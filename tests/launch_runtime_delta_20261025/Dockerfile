FROM python:3.13.5-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY scoremax_runtime_v669b/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY scoremax_runtime_v669b /app
COPY tests/launch_runtime_delta_20261025/native_startup.py /checks/native_startup.py
COPY tests/test_invite_only_pilot.py /checks/tests/test_invite_only_pilot.py
COPY tests/test_programme_practice_routing.py /checks/tests/test_programme_practice_routing.py
COPY ux_vnext_overlay/invite_only_pilot_runtime.py /checks/ux_vnext_overlay/invite_only_pilot_runtime.py
COPY scripts/scoremax_persistent_storage_guard.py scripts/backup_capacity_v1.py /checks/native_guard/
WORKDIR /app
CMD ["python","-B","/checks/native_startup.py"]
