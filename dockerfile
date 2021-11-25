FROM python:latest
WORKDIR /Discord_Auditor
COPY . /Discord_Auditor
RUN pip install -r requirements.txt
CMD python discord_auditor.py