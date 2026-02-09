"""
Agent Tracing Module - 可观测性追踪

使用 Langfuse 追踪 Agent 执行过程：
- Router 决策过程
- Collector 收集过程
- 字段状态变化
- 阶段跳转
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager
from functools import wraps
import json

from app.config import settings

logger = logging.getLogger(__name__)

# Langfuse client (lazy initialization)
_langfuse_client = None


def get_langfuse():
    """Get or create Langfuse client"""
    global _langfuse_client

    if not settings.langfuse_enabled:
        return None

    if _langfuse_client is None:
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host
            )
            logger.info("Langfuse client initialized successfully")
        except ImportError:
            logger.warning("Langfuse not installed. Run: pip install langfuse")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")
            return None

    return _langfuse_client


class AgentTrace:
    """Agent execution trace context"""

    def __init__(
        self,
        session_id: str,
        user_message: str,
        trace_name: str = "chat_turn"
    ):
        self.session_id = session_id
        self.user_message = user_message
        self.trace_name = trace_name
        self.start_time = datetime.now()
        self.trace = None
        self.spans = {}

        # Initialize Langfuse trace
        langfuse = get_langfuse()
        if langfuse:
            self.trace = langfuse.trace(
                name=trace_name,
                session_id=session_id,
                input={"user_message": user_message},
                metadata={"start_time": self.start_time.isoformat()}
            )

    def start_span(
        self,
        name: str,
        input_data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        """Start a new span within the trace"""
        if self.trace:
            span = self.trace.span(
                name=name,
                input=input_data,
                metadata=metadata
            )
            span_id = f"{name}_{datetime.now().timestamp()}"
            self.spans[span_id] = span
            return span_id
        return None

    def end_span(
        self,
        span_id: str,
        output_data: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ):
        """End a span with output"""
        if span_id and span_id in self.spans:
            span = self.spans[span_id]
            span.end(output=output_data, metadata=metadata)

    def log_router_decision(
        self,
        fields_status: Dict[str, Any],
        router_output: Dict[str, Any],
        llm_response: str = None
    ):
        """Log Router decision details"""
        if self.trace:
            self.trace.span(
                name="router_decision",
                input={
                    "fields_status_summary": self._summarize_fields(fields_status),
                    "user_message": self.user_message
                },
                output={
                    "intent": router_output.get("intent"),
                    "extracted_fields": list(router_output.get("extracted_fields", {}).keys()),
                    "guide_to_field": router_output.get("response_strategy", {}).get("guide_to_field"),
                    "agent_type": router_output.get("response_strategy", {}).get("agent_type"),
                    "user_emotion": router_output.get("user_emotion"),
                    "current_phase": router_output.get("current_phase")
                },
                metadata={
                    "llm_raw_response": llm_response[:1000] if llm_response else None
                }
            )

    def log_collector_action(
        self,
        target_field: str,
        next_field: str,
        updated_fields: Dict[str, Any],
        validation_results: Dict[str, Any] = None,
        decision_source: str = "router"
    ):
        """Log Collector action details"""
        if self.trace:
            self.trace.span(
                name="collector_action",
                input={
                    "target_field": target_field,
                    "decision_source": decision_source
                },
                output={
                    "next_field": next_field,
                    "fields_updated": list(validation_results.keys()) if validation_results else [],
                    "fields_status_summary": self._summarize_fields(updated_fields)
                },
                metadata={
                    "validation_results": {
                        k: {"status": v.get("status"), "message": v.get("message")}
                        for k, v in (validation_results or {}).items()
                    }
                }
            )

    def log_phase_transition(
        self,
        from_phase: int,
        to_phase: int,
        reason: str,
        missing_fields: List[str] = None
    ):
        """Log phase transition"""
        if self.trace:
            phase_names = {
                0: "OPENING",
                1: "PEOPLE_COUNT",
                2: "ADDRESS",
                3: "DATE",
                4: "ITEMS",
                5: "OTHER_INFO",
                6: "CONFIRMATION"
            }
            self.trace.span(
                name="phase_transition",
                input={
                    "from_phase": from_phase,
                    "from_phase_name": phase_names.get(from_phase, "UNKNOWN")
                },
                output={
                    "to_phase": to_phase,
                    "to_phase_name": phase_names.get(to_phase, "UNKNOWN"),
                    "reason": reason,
                    "missing_fields": missing_fields
                }
            )

    def log_field_update(
        self,
        field_name: str,
        old_value: Any,
        new_value: Any,
        old_status: str,
        new_status: str
    ):
        """Log individual field update"""
        if self.trace:
            self.trace.event(
                name="field_update",
                input={
                    "field_name": field_name,
                    "old_value": self._safe_serialize(old_value),
                    "old_status": old_status
                },
                output={
                    "new_value": self._safe_serialize(new_value),
                    "new_status": new_status
                }
            )

    def log_completion_check(
        self,
        completion_info: Dict[str, Any]
    ):
        """Log completion check result"""
        if self.trace:
            self.trace.span(
                name="completion_check",
                output={
                    "can_submit": completion_info.get("can_submit"),
                    "completion_rate": completion_info.get("completion_rate"),
                    "missing_fields": completion_info.get("missing_fields"),
                    "next_priority_field": completion_info.get("next_priority_field")
                }
            )

    def log_llm_call(
        self,
        agent_name: str,
        model: str,
        messages: List[Dict],
        response: str,
        tokens_used: int = None,
        latency_ms: float = None
    ):
        """Log LLM API call"""
        if self.trace:
            # Use generation for LLM calls
            self.trace.generation(
                name=f"{agent_name}_llm_call",
                model=model,
                input=messages,
                output=response,
                metadata={
                    "tokens_used": tokens_used,
                    "latency_ms": latency_ms
                }
            )

    def end(
        self,
        output: Dict[str, Any] = None,
        status: str = "success"
    ):
        """End the trace"""
        if self.trace:
            self.trace.update(
                output=output,
                metadata={
                    "status": status,
                    "duration_ms": (datetime.now() - self.start_time).total_seconds() * 1000
                }
            )

    def _summarize_fields(self, fields_status: Dict[str, Any]) -> Dict[str, str]:
        """Create a summary of fields status"""
        summary = {}

        # People count
        pc_status = fields_status.get("people_count_status", "not_collected")
        pc_value = fields_status.get("people_count")
        summary["people_count"] = f"{pc_status}" + (f" ({pc_value})" if pc_value else "")

        # From address
        from_addr = fields_status.get("from_address", {})
        if isinstance(from_addr, dict):
            fa_status = from_addr.get("status", "not_collected")
            fa_value = from_addr.get("value", "")[:20] if from_addr.get("value") else ""
            fa_postal = from_addr.get("postal_code", "")
            fa_building = from_addr.get("building_type", "")
            summary["from_address"] = f"{fa_status}" + (f" ({fa_value}...)" if fa_value else "")
            summary["from_building_type"] = fa_building or "not_collected"
        else:
            summary["from_address"] = "not_collected"

        # To address
        to_addr = fields_status.get("to_address", {})
        if isinstance(to_addr, dict):
            ta_status = to_addr.get("status", "not_collected")
            ta_value = to_addr.get("value", "")[:20] if to_addr.get("value") else ""
            summary["to_address"] = f"{ta_status}" + (f" ({ta_value}...)" if ta_value else "")
        else:
            summary["to_address"] = "not_collected"

        # Move date
        move_date = fields_status.get("move_date", {})
        if isinstance(move_date, dict):
            md_status = move_date.get("status", "not_collected")
            md_value = move_date.get("value", "")
            summary["move_date"] = f"{md_status}" + (f" ({md_value})" if md_value else "")
        else:
            summary["move_date"] = "not_collected"

        # Items
        items = fields_status.get("items", {})
        if isinstance(items, dict):
            items_status = items.get("status", "not_collected")
            items_count = len(items.get("list", []))
            summary["items"] = f"{items_status} ({items_count} items)"
        else:
            summary["items"] = "not_collected"

        # Floor elevator
        from_floor = fields_status.get("from_floor_elevator", {})
        if isinstance(from_floor, dict):
            ff_status = from_floor.get("status", "not_collected")
            ff_floor = from_floor.get("floor")
            ff_elevator = from_floor.get("has_elevator")
            summary["from_floor_elevator"] = f"{ff_status}" + (f" (F{ff_floor}, elevator={ff_elevator})" if ff_floor else "")
        else:
            summary["from_floor_elevator"] = "not_collected"

        to_floor = fields_status.get("to_floor_elevator", {})
        if isinstance(to_floor, dict):
            tf_status = to_floor.get("status", "not_collected")
            summary["to_floor_elevator"] = tf_status
        else:
            summary["to_floor_elevator"] = "not_collected"

        # Packing service
        packing = fields_status.get("packing_service")
        packing_status = fields_status.get("packing_service_status", "not_collected")
        summary["packing_service"] = f"{packing_status}" + (f" ({packing})" if packing else "")

        # Special notes
        special_notes = fields_status.get("special_notes", [])
        special_done = fields_status.get("special_notes_done", False)
        summary["special_notes"] = f"{'done' if special_done else 'not_done'} ({len(special_notes)} notes)"

        return summary

    def _safe_serialize(self, value: Any) -> Any:
        """Safely serialize value for logging"""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, (list, dict)):
            try:
                return json.loads(json.dumps(value, default=str))
            except:
                return str(value)
        return str(value)


class TracingMiddleware:
    """Middleware to add tracing to WebSocket handlers"""

    @staticmethod
    def create_trace(session_id: str, user_message: str) -> AgentTrace:
        """Create a new trace for a chat turn"""
        return AgentTrace(
            session_id=session_id,
            user_message=user_message,
            trace_name="chat_turn"
        )


# Convenience functions
def create_trace(session_id: str, user_message: str) -> AgentTrace:
    """Create a new agent trace"""
    return AgentTrace(session_id=session_id, user_message=user_message)


def flush_traces():
    """Flush pending traces to Langfuse"""
    langfuse = get_langfuse()
    if langfuse:
        langfuse.flush()


# Debug logging (always available, even without Langfuse)
class DebugTracer:
    """Simple debug tracer that logs to console/file"""

    def __init__(self, session_id: str, enabled: bool = True):
        self.session_id = session_id
        self.enabled = enabled
        self.events = []

    def log(self, event_type: str, data: Dict[str, Any]):
        """Log an event"""
        if not self.enabled:
            return

        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "data": data
        }
        self.events.append(event)

        # Also log to standard logger
        logger.info(f"[TRACE:{self.session_id[:8]}] {event_type}: {json.dumps(data, ensure_ascii=False, default=str)[:500]}")

    def log_router(
        self,
        user_message: str,
        fields_status: Dict[str, Any],
        intent: str,
        extracted_fields: List[str],
        guide_to_field: str,
        emotion: str
    ):
        """Log Router decision"""
        self.log("ROUTER_DECISION", {
            "user_message": user_message[:100],
            "intent": intent,
            "extracted_fields": extracted_fields,
            "guide_to_field": guide_to_field,
            "emotion": emotion
        })

    def log_collector(
        self,
        target_field: str,
        next_field: str,
        decision_source: str,
        updated_fields: List[str]
    ):
        """Log Collector action"""
        self.log("COLLECTOR_ACTION", {
            "target_field": target_field,
            "next_field": next_field,
            "decision_source": decision_source,
            "updated_fields": updated_fields
        })

    def log_phase(
        self,
        from_phase: int,
        to_phase: int,
        completion_rate: float,
        missing_fields: List[str]
    ):
        """Log phase transition"""
        phase_names = {
            0: "OPENING", 1: "PEOPLE_COUNT", 2: "ADDRESS",
            3: "DATE", 4: "ITEMS", 5: "OTHER_INFO", 6: "CONFIRMATION"
        }
        self.log("PHASE_TRANSITION", {
            "from": f"{from_phase} ({phase_names.get(from_phase, '?')})",
            "to": f"{to_phase} ({phase_names.get(to_phase, '?')})",
            "completion_rate": f"{completion_rate:.1%}",
            "missing_fields": missing_fields
        })

    def get_summary(self) -> str:
        """Get summary of all events"""
        if not self.events:
            return "No events recorded"

        summary = [f"\n{'='*60}", f"Trace Summary for Session: {self.session_id}", f"{'='*60}"]

        for event in self.events:
            summary.append(f"\n[{event['timestamp']}] {event['event_type']}")
            for key, value in event['data'].items():
                summary.append(f"  {key}: {value}")

        summary.append(f"\n{'='*60}\n")
        return "\n".join(summary)
