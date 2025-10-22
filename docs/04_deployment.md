# Chapter 4: Deployment

Production deployment guide for Video Agent, covering local, cloud, and containerized setups.

---

## Local Development

### Quick Start

```bash
# Clone and setup
git clone https://github.com/zhwa/video-agent.git
cd video-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run with dummy providers
python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out
```

### Development Configuration

Create `.env` file in project root:

```bash
# Local development settings
GOOGLE_API_KEY=your-api-key-here
CACHE_ENABLED=true
CACHE_DIR=workspace/cache
RUNS_DIR=workspace/runs
LOG_LEVEL=DEBUG
MAX_WORKERS=4
```

Load environment variables:
```bash
# Linux/Mac
export $(cat .env | xargs)

# Windows PowerShell
Get-Content .env | ForEach-Object { 
    $name, $value = $_.Split('=')
    [Environment]::SetEnvironmentVariable($name, $value)
}
```

---

## Docker Deployment

### Dockerfile

Create `Dockerfile` in project root:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Default command
ENTRYPOINT ["python", "-m", "agent.cli"]
CMD ["--help"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  video-agent:
    build: .
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - MAX_WORKERS=4
      - CACHE_ENABLED=true
    volumes:
      - ./workspace:/app/workspace
      - ./inputs:/app/inputs:ro
    command: >
      python -m agent.cli 
      /app/inputs/lecture.md 
      --full-pipeline 
      --out /app/workspace/out
    
    # Optional: GPU support
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]
```

### Build and Run

```bash
# Build image
docker build -t video-agent:latest .

# Run container
docker run \
  -e GOOGLE_API_KEY=your-api-key-here \
  -v $(pwd)/workspace:/app/workspace \
  -v $(pwd)/inputs:/app/inputs \
  video-agent:latest \
  /app/inputs/lecture.md --full-pipeline --out /app/workspace/out

# Using Docker Compose
docker-compose up
```

---

## Cloud Deployment

### Google Cloud Run

**Prerequisites**:
- Google Cloud project
- Docker image pushed to Google Container Registry (GCR)
- Cloud Storage bucket for artifacts

**Deploy to Cloud Run**:

```bash
# 1. Build and push to GCR
gcloud builds submit --tag gcr.io/YOUR_PROJECT/video-agent

# 2. Deploy to Cloud Run
gcloud run deploy video-agent \
  --image gcr.io/YOUR_PROJECT/video-agent \
  --memory 4Gi \
  --timeout 3600 \
  --set-env-vars GOOGLE_API_KEY=${GOOGLE_API_KEY} \
  --service-account video-agent-sa@YOUR_PROJECT.iam.gserviceaccount.com
```

**Cloud Run Configuration** (`cloudrun.yaml`):

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: video-agent
spec:
  template:
    spec:
      serviceAccountName: video-agent-sa
      containers:
      - image: gcr.io/YOUR_PROJECT/video-agent
        resources:
          limits:
            memory: 4Gi
            cpu: 4
        env:
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              name: google-api-key
              key: key
        timeoutSeconds: 3600
```

**Cost Estimation** (per 1-hour run):
- 4 vCPU @ $0.00002376/sec = ~$0.34
- 4 GB memory @ $0.00000521/sec = ~$0.19
- Storage (10 videos @ 100MB): ~$0.05
- **Total: ~$0.60 per video**

### AWS Lambda (Batch Processing)

**Alternative**: Use AWS Lambda for shorter pipelines:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  VideoAgentFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.9
      MemorySize: 3008
      Timeout: 900
      EphemeralStorage:
        Size: 10240
      Handler: lambda_handler.main
      Environment:
        Variables:
          GOOGLE_API_KEY: ${GOOGLE_API_KEY}
```

**Limitations**:
- 15 min timeout (too short for full pipeline)
- Better for script generation only

### Kubernetes (High Volume)

Deploy on Kubernetes for horizontal scaling:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: video-agent-config
data:
  max-workers: "8"
  cache-enabled: "true"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: video-agent-processor
spec:
  replicas: 3
  selector:
    matchLabels:
      app: video-agent
  template:
    metadata:
      labels:
        app: video-agent
    spec:
      containers:
      - name: video-agent
        image: gcr.io/YOUR_PROJECT/video-agent:latest
        resources:
          requests:
            memory: "4Gi"
            cpu: "4"
          limits:
            memory: "8Gi"
            cpu: "8"
        envFrom:
        - configMapRef:
            name: video-agent-config
        volumeMounts:
        - name: cache
          mountPath: /app/workspace/cache
      volumes:
      - name: cache
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: video-agent-service
spec:
  selector:
    app: video-agent
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8080
```

**Scaling Strategy**:
- Horizontal scaling: 3-10 replicas
- Load balancing: Distribute jobs across workers
- Cache sharing: Use GCS for distributed cache

---

## Configuration Management

### Environment Variables

**Development**:
```bash
GOOGLE_API_KEY=your-api-key-here
LOG_LEVEL=DEBUG
CACHE_ENABLED=true
MAX_WORKERS=2
```

**Staging**:
```bash
GOOGLE_API_KEY=your-api-key-here
LOG_LEVEL=INFO
CACHE_ENABLED=true
MAX_WORKERS=4
```

**Production**:
```bash
GOOGLE_API_KEY=your-api-key-here
LOG_LEVEL=WARNING
CACHE_ENABLED=true
MAX_WORKERS=8
SLIDE_RATE_LIMIT=10
```

### Secret Management

**Google Cloud Secret Manager**:

```bash
# Store secrets
gcloud secrets create google-api-key --data-file=- <<< $GOOGLE_API_KEY

# Grant access
gcloud secrets add-iam-policy-binding google-api-key \
  --member=serviceAccount:video-agent@YOUR_PROJECT.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

**Reference in deployment**:
```yaml
env:
- name: GOOGLE_API_KEY
  valueFrom:
    secretKeyRef:
      name: google-api-key
      key: secret
```

### Configuration Files

**YAML Configuration** (`config/deployment.yaml`):

```yaml
deployment:
  environment: production
  region: us-central1
  
google:
  api_key: ${GOOGLE_API_KEY}
  model: gemini-2.0-flash-exp
  max_retries: 3
  timeout: 30
  
processing:
  max_workers: 8
  max_slide_workers: 4
  cache_enabled: true
  cache_ttl: 86400  # 24 hours
  
monitoring:
  log_level: WARNING
  metrics_enabled: true
  traces_enabled: true
```

Load configuration:
```python
import yaml

with open('config/deployment.yaml') as f:
    config = yaml.safe_load(f)
```

---

## Monitoring & Logging

### Structured Logging

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': record.created,
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
        })

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
```

**Output**:
```json
{"timestamp": 1697865600, "level": "INFO", "message": "Processing chapter 1", "module": "cli"}
{"timestamp": 1697865605, "level": "INFO", "message": "Generated 5 slides", "module": "script_generator"}
```

### Google Cloud Logging

```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit 50

# Filter by severity
gcloud logging read "resource.type=cloud_run_revision AND severity=ERROR"
```

### Metrics

**Key Metrics to Track**:
- Processing time per chapter
- API cost per video
- Cache hit rate
- Error rate

**Example Metric Collection**:

```python
from google.cloud import monitoring_v3

client = monitoring_v3.MetricServiceClient()

# Record metric
series = monitoring_v3.TimeSeries()
series.metric.type = 'custom.googleapis.com/video-agent/processing-time'
series.resource.type = 'global'

# Add data point
now = time.time()
seconds = int(now)
nanos = int((now - seconds) * 10 ** 9)
interval = monitoring_v3.TimeInterval({"end_time": {"seconds": seconds, "nanos": nanos}})
point = monitoring_v3.Point({"interval": interval, "value": {"double_value": 123.4}})
series.points = [point]

client.create_time_series(name=project_name, time_series=[series])
```

---

## Scaling Considerations

### Performance Tuning

**CPU/Memory Allocation**:
| Task | CPU | Memory | Rationale |
|------|-----|--------|-----------|
| Script Gen (LLM only) | 2 | 2GB | I/O bound (API calls) |
| Image Gen (parallel) | 4 | 4GB | Slightly CPU intensive |
| Video Compose (moviepy) | 4 | 8GB | CPU/memory intensive |
| Full Pipeline | 8 | 8GB | Recommended minimum |

**Parallelization**:
```bash
# Optimal for 4-core machine
--max-workers 4 --max-slide-workers 2

# Optimal for 8-core machine
--max-workers 8 --max-slide-workers 4

# Optimal for 16-core machine
--max-workers 16 --max-slide-workers 8
```

### Cost Optimization

**Strategy 1: Use Caching**
- 60%+ speedup with cache hits
- Massive cost reduction on repeated content

**Strategy 2: Batch Processing**
- Process multiple videos overnight
- Use cheaper off-peak pricing

**Strategy 3: Monitor API Usage**
- Track Google API quotas in Cloud Console
- Set up billing alerts
- Use caching to minimize repeated calls

**Example Cost Breakdown** (100-slide video):

| Service | Cost | Notes |
|----------|------|-------|
| Google Gemini LLM | $0.10 | $0.001/slide × 100 |
| Google Cloud TTS | $0.01 | $0.0001/slide × 100 |
| Google Imagen 3 | $1.00 | $0.01/image × 100 (fast mode) |
| Storage (Local) | $0.00 | Local file storage |
| **Total** | **$1.11** | Per video |

**Note**: Costs are approximate and vary based on:
- Model selection (gemini-2.0-flash-exp vs gemini-1.5-pro)
- Image quality (fast mode vs high quality)
- Content length and complexity

---

## Disaster Recovery

### Backup Strategy

```bash
# Backup cache
gsutil -m cp -r workspace/cache gs://my-backups/cache/

# Backup runs
gsutil -m cp -r workspace/runs gs://my-backups/runs/

# Scheduled backup (cron)
0 2 * * * gsutil -m cp -r /app/workspace gs://my-backups/$(date +\%Y-\%m-\%d)
```

### Resume from Checkpoint

```bash
# List available runs
python -m agent.cli --list-runs

# Resume specific run
python -m agent.cli input.md --full-pipeline --resume run_id_abc123

# Resume with one worker (safer)
python -m agent.cli input.md --full-pipeline --resume run_id_abc123 --max-workers 1
```

### Failure Handling

**Automatic Retry**:
```python
LLM_MAX_RETRIES=5        # Retry failed LLM calls 5 times
SLIDE_RATE_LIMIT=5        # Reduce rate limit on 429 errors
```

**Manual Intervention**:
```bash
# Run failed chapter again
python -m agent.cli input.md --resume run_id_abc123 --max-workers 1

# Skip failed chapter and continue
# (Manual: edit workspace/runs/run_id_abc123/checkpoint.json)
```

---

## Security Considerations

### API Keys Management

**Never commit secrets**:
```bash
# .gitignore
.env
credentials.json
config/local.yaml
```

**Use environment variables**:
```python
import os
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY not set")
```

### Service Accounts

**Create dedicated service account**:

```bash
# GCP
gcloud iam service-accounts create video-agent-sa
gcloud projects add-iam-policy-binding YOUR_PROJECT \
  --member=serviceAccount:video-agent-sa@YOUR_PROJECT.iam.gserviceaccount.com \
  --role=roles/aiplatform.user

# Create key
gcloud iam service-accounts keys create key.json \
  --iam-account=video-agent-sa@YOUR_PROJECT.iam.gserviceaccount.com
```

**Minimal Permissions**:
```bash
# Only grant necessary permissions
roles/aiplatform.user          # Vertex AI access
roles/storage.admin            # GCS access
roles/logging.logWriter        # Cloud Logging
roles/monitoring.metricWriter  # Cloud Monitoring
```

### Network Security

**Firewall Rules**:
```bash
gcloud compute firewall-rules create video-agent-internal \
  --allow tcp:8080 \
  --source-ranges 10.0.0.0/8 \
  --target-tags video-agent
```

**Private GCS Bucket**:
```bash
gsutil iam ch serviceAccount:video-agent@YOUR_PROJECT.iam.gserviceaccount.com:objectViewer gs://my-bucket
```

---

## Troubleshooting Deployments

### Issue: "Out of Memory"

**Solution 1**: Increase memory allocation
```bash
# Cloud Run
gcloud run deploy video-agent --memory 8Gi

# Docker
docker run -m 8g video-agent:latest
```

**Solution 2**: Reduce parallelization
```bash
--max-workers 2 --max-slide-workers 1
```

### Issue: "API Rate Limit Exceeded"

**Solution**:
```bash
export SLIDE_RATE_LIMIT=5  # Slow down API calls
```

### Issue: "Disk Space Full"

**Solution 1**: Increase disk size
```bash
# Cloud Run (change ephemeral storage)
gcloud run deploy video-agent --ephemeral-storage 10Gi

# Docker
docker run --device-write-bps /dev/sda:10mb video-agent
```

**Solution 2**: Enable streaming output to storage
```bash
export STORAGE_PROVIDER=gcs
```

### Issue: "Timeout (job killed after 1 hour)"

**Solution**:
- Split into smaller jobs (fewer chapters)
- Use resume functionality
- Increase timeout on container

```bash
# Cloud Run - extend timeout
gcloud run deploy video-agent --timeout 3600
```

---

## Performance Checklist

- [ ] Set up Google API key with appropriate quotas
- [ ] Enable caching for repeated content
- [ ] Set appropriate `--max-workers` for machine
- [ ] Monitor API usage in Google Cloud Console
- [ ] Set up billing alerts
- [ ] Monitor logs in Cloud Logging (if deployed to GCP)
- [ ] Set up alerts for failures
- [ ] Backup runs/cache regularly
- [ ] Test resume functionality
- [ ] Plan for disaster recovery

---

**Next**: See [Chapter 5: Testing](05_testing.md) for testing strategies.
