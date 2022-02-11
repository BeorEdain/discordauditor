FROM python:latest
COPY . /Discord_Auditor
WORKDIR /Discord_Auditor
RUN pip install -r requirements.txt
CMD python discord_auditor.py