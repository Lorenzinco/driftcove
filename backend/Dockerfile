FROM python:3-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apk add --no-cache \
    bash \
    ca-certificates \
    iproute2 \
    nftables \
    py3-nftables \
    tcpdump \
    wireguard-tools && \
    mkdir -p /etc/wireguard

RUN python3 - <<'PY'
import pathlib
import shutil
import sysconfig

python_site = pathlib.Path(sysconfig.get_paths()["purelib"])
candidates = list(pathlib.Path("/usr/lib").glob("python*/site-packages/nftables*"))
if not candidates:
    raise SystemExit("py3-nftables was installed but no nftables Python binding was found")
for source in candidates:
    target = python_site / source.name
    if target.exists():
        continue
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)
PY

COPY ./requirements.txt /home/requirements.txt

RUN python3 -m pip install --no-cache-dir -r /home/requirements.txt
COPY . /home/backend
WORKDIR /home
RUN chmod +x /home/backend/init.sh

ENV PYTHONPATH=/home
CMD ["bash", "/home/backend/init.sh"]
