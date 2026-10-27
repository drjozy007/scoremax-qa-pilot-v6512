FROM python:3.13.5-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY scoremax_runtime_v669b/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY scoremax_runtime_v669b /app
COPY biology_accepted_public_runtime_20261027 /accepted
COPY tests/biology_receiver_20261027 /checks/tests/biology_receiver_20261027
COPY scripts/qualify_assessment_contract_repair.py scripts/qualify_native_manifest_pull.py /checks/scripts/
COPY scripts/scoremax_persistent_storage_guard.py scripts/backup_capacity_v1.py /checks/native_guard/
CMD ["python","-B","/checks/tests/biology_receiver_20261027/run_linux.py"]
