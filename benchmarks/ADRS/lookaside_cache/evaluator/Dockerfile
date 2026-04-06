FROM python:3.12-slim
WORKDIR /benchmark

RUN apt-get update \
    && apt-get install -y --no-install-recommends wget gnupg ca-certificates apt-transport-https \
    && wget https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends dotnet-sdk-8.0 \
    && dotnet tool install --global p \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.dotnet/tools:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x evaluate.sh

ENTRYPOINT ["./evaluate.sh"]
