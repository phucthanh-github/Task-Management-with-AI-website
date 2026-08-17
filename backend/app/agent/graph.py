import json
import httpx
import re
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime, timedelta
from langgraph.graph import StateGraph, END
from huggingface_hub import AsyncInferenceClient

from ..config import settings
from .tools import execute_info_tool, execute_action_tool
from .prompts import get_system_prompt
from ..utils import utc_now

# Define the State format for LangGraph
class AgentState(TypedDict):
    messages: List[Dict[str, str]]        # Recent messages in the thread (max 10)
    user_id: str                          # Owner of the conversation
    todos: List[Dict[str, Any]]           # Contextual current tasks list
    tool_calls: List[Dict[str, Any]]      # Extracted tool calls to be executed
    final_response: str                   # Response to send back to the user
    should_refresh: bool                  # Hint for frontend to reload todo lists
    hf_token: str                         # User's HF API Token

async def call_hugging_face_api(prompt: str, system_prompt: str, hf_token: str) -> str:
    """
    Calls the Hugging Face serverless inference endpoint using the user's custom Token.
    """
    if not hf_token or hf_token.strip() == "":
        raise ValueError("Hugging Face token is not provided.")

    client = AsyncInferenceClient(model=settings.HF_MODEL, token=hf_token)
    res = await client.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=800
    )
    return res.choices[0].message.content

def parse_llm_json(raw_text: str) -> List[Dict[str, Any]]:
    """
    Parses JSON output from LLM, cleaning any Markdown formatting wrapper if present.
    Extracts all JSON objects by brace-counting and returns them as a list of dicts.
    """
    cleaned = raw_text.strip()
    
    # Remove markdown code blocks if present (e.g. ```json ... ```)
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    cleaned = cleaned.strip()
    
    # Try parsing the whole string first
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return [data]
        elif isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except json.JSONDecodeError:
        pass
        
    # Brace counting parser to extract multiple JSON objects
    results = []
    brace_count = 0
    start_idx = -1
    
    for i, char in enumerate(cleaned):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            if brace_count > 0:
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    json_str = cleaned[start_idx:i+1]
                    try:
                        obj = json.loads(json_str)
                        if isinstance(obj, dict):
                            results.append(obj)
                    except json.JSONDecodeError:
                        pass
                    start_idx = -1
                    
    if results:
        return results
        
    raise ValueError(f"Could not parse text as JSON: {raw_text}")

def rule_based_fallback(query: str, todos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Rule-based chatbot backup for local run if Hugging Face token is not set or API fails.
    Supports basic Todo CRUD operations in Vietnamese.
    """
    query_lower = query.lower()
    
    # 1. CREATE TASK
    if "tạo" in query_lower or "thêm" in query_lower or "create" in query_lower:
        # Try to extract title: look for text after "tạo công việc" or "thêm công việc" or "tạo" / "thêm"
        title = "Công việc mới từ Chatbot"
        match = re.search(r"(?:tạo công việc|thêm công việc|tạo|thêm)\s+(.+)", query, re.IGNORECASE)
        if match:
            title = match.group(1).split("vào lúc")[0].split("hạn chót")[0].strip()
        
        # Simple deadline parsing
        deadline_iso = None
        now = utc_now()
        if "ngày mai" in query_lower:
            tomorrow = now + timedelta(days=1)
            tomorrow = tomorrow.replace(hour=17, minute=0, second=0)
            deadline_iso = tomorrow.isoformat()
        elif "hôm nay" in query_lower:
            today = now.replace(hour=23, minute=59, second=0)
            deadline_iso = today.isoformat()
            
        return {
            "tool": "ActionTool",
            "parameters": {
                "action": "create",
                "title": title,
                "description": "Được tạo tự động qua Chatbot (Chế độ Fallback)",
                "deadline": deadline_iso
            }
        }
        
    # 2. DELETE TASK
    elif "xóa" in query_lower or "delete" in query_lower or "hủy" in query_lower:
        # Search task matching keyword
        matched_todo = None
        for todo in todos:
            if todo["title"].lower() in query_lower or query_lower in todo["title"].lower():
                matched_todo = todo
                break
        
        if matched_todo:
            return {
                "tool": "ActionTool",
                "parameters": {
                    "action": "delete",
                    "todo_id": matched_todo["id"]
                }
            }
        else:
            return {
                "tool": "InforTool",
                "parameters": {
                    "response": "Tôi không tìm thấy công việc nào khớp với mô tả của bạn để xóa. Vui lòng ghi rõ tên công việc."
                }
            }
            
    # 3. UPDATE TASK (Complete status)
    elif "hoàn thành" in query_lower or "xong" in query_lower or "complete" in query_lower:
        matched_todo = None
        for todo in todos:
            if todo["title"].lower() in query_lower or query_lower in todo["title"].lower():
                matched_todo = todo
                break
                
        if matched_todo:
            return {
                "tool": "ActionTool",
                "parameters": {
                    "action": "update",
                    "todo_id": matched_todo["id"],
                    "status": "completed"
                }
            }
        else:
            return {
                "tool": "InforTool",
                "parameters": {
                    "response": "Tôi không tìm thấy công việc nào phù hợp để đánh dấu hoàn thành."
                }
            }
            
    # 4. INFO / CHITCHAT / LIST ALL
    else:
        if "danh sách" in query_lower or "liệt kê" in query_lower or "có việc gì" in query_lower or "show" in query_lower or "list" in query_lower:
            if not todos:
                res = "Bạn hiện không có công việc nào trong danh sách."
            else:
                res = "Dưới đây là danh sách công việc của bạn:\n"
                for i, todo in enumerate(todos, 1):
                    dl = f" (Hạn chót: {todo['deadline'].strftime('%d/%m/%Y %H:%M')})" if todo.get("deadline") else " (Không có hạn)"
                    status_text = "Đã xong" if todo['status'] == "completed" else "Đang làm" if todo['status'] == "in_progress" else "Chưa làm"
                    res += f"{i}. [{status_text}] {todo['title']}{dl} [ID: {todo['id']}]\n"
            return {
                "tool": "InforTool",
                "parameters": {
                    "response": res
                }
            }
        
        # Standard welcome
        return {
            "tool": "InforTool",
            "parameters": {
                "response": "Xin chào! Tôi là trợ lý AI. Bạn có thể trò chuyện với tôi hoặc yêu cầu tôi tạo, sửa, xóa công việc."
            }
        }

# --- GRAPH NODES ---

async def llm_node(state: AgentState) -> Dict[str, Any]:
    """
    LLM Node: Evaluates user intent and schedules tool execution in one single step.
    """
    # 1. Extract inputs
    user_query = state["messages"][-1]["content"] if state["messages"] else ""
    todos = state["todos"]
    user_id = state["user_id"]
    
    # 2. Format Context Todos
    todos_context = []
    for t in todos:
        # Handle deadline display
        dl = t.get("deadline")
        dl_str = dl.isoformat() if isinstance(dl, datetime) else str(dl) if dl else "Không có"
        todos_context.append({
            "id": t.get("id"),
            "title": t.get("title"),
            "description": t.get("description", ""),
            "status": t.get("status", "pending"),
            "deadline": dl_str
        })
        
    # 3. Build Chat History
    chat_history_str = ""
    # We only show last 10 messages for context
    history = state["messages"][:-1]  # Exclude current message
    for msg in history[-10:]:
        role = "Người dùng" if msg["sender"] == "user" else "Trợ lý AI"
        chat_history_str += f"{role}: {msg['content']}\n"

    # Current Time for deadline reference
    current_time_str = utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # 4. Construct System Prompt using template helper
    system_prompt = get_system_prompt(
        current_time=current_time_str,
        todos_context=json.dumps(todos_context, ensure_ascii=False, indent=2),
        chat_history=chat_history_str
    )

    tool_calls = []
    should_refresh = False
    hf_token = state.get("hf_token", "").strip()

    if not hf_token:
        return {
            "tool_calls": [{
                "name": "InforTool",
                "parameters": {
                    "response": "Vui lòng nhập cấu hình Hugging Face Token cá nhân của bạn để sử dụng tính năng Chatbot AI."
                }
            }],
            "should_refresh": False
        }
    
    # 5. Execute LLM Call or Fallback
    try:
        raw_output = await call_hugging_face_api(user_query, system_prompt, hf_token)
        parsed_list = parse_llm_json(raw_output)
        
        for parsed in parsed_list:
            tool_name = parsed.get("tool")
            params = parsed.get("parameters", {})
            
            # Inject user_id into action tool parameters
            if tool_name == "ActionTool":
                params["user_id"] = user_id
                should_refresh = True
                
            tool_calls.append({
                "name": tool_name,
                "parameters": params
            })
    except Exception as e:
        print(f"[AI Agent] LLM invocation failed. Error: {e}")
        # If it's a authentication/token issue, return a direct error response
        err_msg = str(e)
        if "401" in err_msg or "unauthorized" in err_msg.lower() or "token" in err_msg.lower():
            return {
                "tool_calls": [{
                    "name": "InforTool",
                    "parameters": {
                        "response": f"Lỗi xác thực Hugging Face: Token của bạn không hợp lệ hoặc đã hết hạn. Chi tiết: {err_msg}"
                    }
                }],
                "should_refresh": False
            }
            
        # Call rule based fallback
        parsed = rule_based_fallback(user_query, todos_context)
        tool_name = parsed["tool"]
        params = parsed["parameters"]
        if tool_name == "ActionTool":
            params["user_id"] = user_id
            should_refresh = True
        tool_calls.append({
            "name": tool_name,
            "parameters": params
        })

    return {
        "tool_calls": tool_calls,
        "should_refresh": should_refresh
    }

async def tool_node(state: AgentState) -> Dict[str, Any]:
    """
    Tool Node: Runs the FIRST tool call in the list, logs its result,
    and removes (pops) it from the list to schedule the next step.
    """
    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        return {}

    # Get the first tool call
    current_tool = tool_calls[0]
    remaining_tools = tool_calls[1:]
    
    name = current_tool.get("name")
    params = current_tool.get("parameters", {})
    
    try:
        if name == "ActionTool":
            # Call action tool function
            res = await execute_action_tool(**params)
        elif name == "InforTool":
            # Call info tool function
            res = await execute_info_tool(**params)
        else:
            res = f"Không nhận diện được tool: {name}"
    except Exception as e:
        res = f"Lỗi khi chạy tool '{name}': {e}"
        
    # Accumulate response in final_response
    prev_response = state.get("final_response") or ""
    if prev_response:
        new_response = prev_response + "\n" + res
    else:
        new_response = res
        
    return {
        "tool_calls": remaining_tools,
        "final_response": new_response
    }

# --- COMPILE STATE GRAPH ---

# Initialize graph builder
builder = StateGraph(AgentState)

# Add node definitions
builder.add_node("llm_node", llm_node)
builder.add_node("tool_node", tool_node)

# Set starting point
builder.set_entry_point("llm_node")

# Routing logic after LLM call and Tool execution
def router(state: AgentState) -> str:
    # If there are still tool calls remaining in the plan, continue executing them.
    # Otherwise, finish the execution.
    if state.get("tool_calls"):
        return "tool_node"
    return "end"

# Establish graph edges
builder.add_conditional_edges(
    "llm_node",
    router,
    {
        "tool_node": "tool_node",
        "end": END
    }
)

# After tool execution, check if there are more tools left in the list
builder.add_conditional_edges(
    "tool_node",
    router,
    {
        "tool_node": "tool_node",
        "end": END
    }
)

# Finalize the compiled Graph
agent_graph = builder.compile()
