FROM python:3.13.5-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY scoremax_runtime_v669b/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY scoremax_runtime_v669b /app
COPY tests/learner_display_delta_20261026 /checks/tests/learner_display_delta_20261026
COPY scripts/scoremax_persistent_storage_guard.py scripts/backup_capacity_v1.py /checks/native_guard/
WORKDIR /app
CMD ["python","-B","/checks/tests/learner_display_delta_20261026/native_startup.py"]
