FROM python:3.13.5-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY scoremax_runtime_v669b/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY scoremax_runtime_v669b /app
COPY tests/paid_ai_marking_20261026 /checks/tests/paid_ai_marking_20261026
COPY ux_vnext_overlay/paid_ai_marking_20261026 /checks/ux_vnext_overlay/paid_ai_marking_20261026
COPY scripts/evaluate_paid_ai_benchmark_20261026.py /checks/scripts/evaluate_paid_ai_benchmark_20261026.py
COPY scripts/scoremax_persistent_storage_guard.py scripts/backup_capacity_v1.py /checks/native_guard/
WORKDIR /app
CMD ["python","-B","/checks/tests/paid_ai_marking_20261026/native_startup.py"]
