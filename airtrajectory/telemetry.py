"""Decision telemetry with a zero-dependency local journal and optional OpenTelemetry spans."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import json, os, time, uuid
from pathlib import Path
from typing import Any, Dict, Optional

@dataclass
class DecisionTrace:
    trace_id: str
    span_name: str
    started_at: float
    ended_at: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: list = field(default_factory=list)
    status: str = "ok"

class DecisionTelemetry:
    def __init__(self, journal_path: str | Path | None = None):
        self.journal_path=Path(journal_path or os.getenv("AIRTRAJECTORY_TRACE_JOURNAL","traces/decisions.jsonl"))
        self.journal_path.parent.mkdir(parents=True,exist_ok=True)

    @contextmanager
    def span(self, name: str, **attributes):
        record=DecisionTrace(uuid.uuid4().hex,name,time.time(),attributes=attributes)
        otel_span=None
        try:
            try:
                from opentelemetry import trace
                otel_span=trace.get_tracer("airtrajectory.decision").start_span(name,attributes={k:str(v) for k,v in attributes.items()})
            except ImportError:
                pass
            yield record
        except Exception as exc:
            record.status="error"; record.events.append({"name":"exception","type":type(exc).__name__,"message":str(exc)})
            if otel_span:
                otel_span.record_exception(exc)
            raise
        finally:
            record.ended_at=time.time()
            if otel_span: otel_span.end()
            with self.journal_path.open("a",encoding="utf-8") as f:
                f.write(json.dumps(asdict(record),ensure_ascii=False,default=str)+"\n")

def configure_otlp(service_name="airtrajectory"):
    """Optional OTLP exporter. Phoenix can receive these spans through its OTLP endpoint."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        raise RuntimeError("install AirTrajectory telemetry extras to enable OTLP export") from exc
    provider=TracerProvider(resource=Resource.create({"service.name":service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    return provider
