from __future__ import annotations

import json
import os
import random
import smtplib
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Dict, List, Literal, Optional, TypedDict

import requests
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None

load_dotenv()


class AgentState(TypedDict, total=False):
    trends: List[Dict[str, Any]]
    scored_niches: List[Dict[str, Any]]
    selected_niche: Dict[str, Any]
    generated_post: Dict[str, Any]
    approval_channel: Literal["email", "whatsapp"]
    approval_token: str
    human_approved: Optional[bool]
    approval_status: Literal["pending", "approved", "rejected"]
    publish_result: Dict[str, Any]
    logs: List[str]


@dataclass
class InstagramPublisher:
    business_account_id: str
    access_token: str
    dry_run: bool = True

    def publish(self, caption: str, image_url: str) -> Dict[str, Any]:
        if self.dry_run:
            return {
                "status": "success",
                "mode": "dry_run",
                "caption_preview": caption[:120],
                "image_url": image_url,
                "instagram_post_id": f"dry_{uuid.uuid4().hex[:10]}",
            }

        create_media_url = f"https://graph.facebook.com/v21.0/{self.business_account_id}/media"
        create_payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.access_token,
        }
        create_resp = requests.post(create_media_url, data=create_payload, timeout=30)
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")

        publish_url = f"https://graph.facebook.com/v21.0/{self.business_account_id}/media_publish"
        publish_payload = {"creation_id": creation_id, "access_token": self.access_token}
        publish_resp = requests.post(publish_url, data=publish_payload, timeout=30)
        publish_resp.raise_for_status()

        return {
            "status": "success",
            "mode": "live",
            "media_creation_id": creation_id,
            "instagram_post_id": publish_resp.json().get("id"),
        }


# -------------------- Trend and niche intelligence --------------------
def fetch_trends() -> List[Dict[str, Any]]:
    # Replace with real APIs (Google Trends / social listening tools)
    seed_data = [
        {"niche": "AI Productivity", "trend_strength": 91, "competition": 62, "audience_fit": 85},
        {"niche": "Fitness for Developers", "trend_strength": 74, "competition": 40, "audience_fit": 79},
        {"niche": "Budget Travel Hacks", "trend_strength": 82, "competition": 67, "audience_fit": 70},
        {"niche": "Healthy High-Protein Recipes", "trend_strength": 88, "competition": 58, "audience_fit": 90},
        {"niche": "Side Hustle Automation", "trend_strength": 93, "competition": 77, "audience_fit": 83},
    ]
    random.shuffle(seed_data)
    return seed_data


def score_niches(trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored = []
    for item in trends:
        virality_score = (
            item["trend_strength"] * 0.5
            + (100 - item["competition"]) * 0.2
            + item["audience_fit"] * 0.3
        )
        scored.append({**item, "virality_score": round(virality_score, 2)})
    scored.sort(key=lambda x: x["virality_score"], reverse=True)
    return scored


def generate_post_content(niche: Dict[str, Any]) -> Dict[str, str]:
    prompt = (
        "Create a concise Instagram post package in JSON with keys: caption, image_prompt, hashtags. "
        f"Niche: {niche['niche']}. Tone: motivational, practical, and viral-friendly."
    )

    if ChatOpenAI and os.getenv("OPENAI_API_KEY"):
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        response = llm.invoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        try:
            parsed = json.loads(content)
            return {
                "caption": parsed.get("caption", ""),
                "image_prompt": parsed.get("image_prompt", ""),
                "hashtags": parsed.get("hashtags", ""),
            }
        except json.JSONDecodeError:
            pass

    # Fallback template for deterministic local demos
    niche_name = niche["niche"]
    return {
        "caption": (
            f"Today's focus: {niche_name}. Save this post if you want actionable growth tips in this niche. "
            "Consistency + clarity beats luck every time."
        ),
        "image_prompt": (
            f"Minimal modern Instagram graphic about {niche_name}, bold typography, high contrast, square format"
        ),
        "hashtags": "#growth #instagramstrategy #contentcreator #viralcontent #aiautomation",
    }


# -------------------- HITL integrations --------------------
def send_email_approval(subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("APPROVAL_FROM_EMAIL")
    recipient = os.getenv("APPROVAL_TO_EMAIL")

    if not all([host, user, password, sender, recipient]):
        raise ValueError("Email variables are missing. Check .env settings for SMTP and email addresses.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def send_whatsapp_approval(message: str) -> None:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_num = os.getenv("TWILIO_WHATSAPP_FROM")
    to_num = os.getenv("TWILIO_WHATSAPP_TO")

    if not all([sid, token, from_num, to_num]):
        raise ValueError("WhatsApp variables are missing. Check .env settings for Twilio credentials.")

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    payload = {"From": from_num, "To": to_num, "Body": message}
    response = requests.post(url, data=payload, auth=(sid, token), timeout=30)
    response.raise_for_status()


# -------------------- LangGraph nodes --------------------
def node_fetch_and_score(state: AgentState) -> AgentState:
    trends = fetch_trends()
    scored = score_niches(trends)
    logs = state.get("logs", []) + ["Fetched trends and scored niches."]
    return {**state, "trends": trends, "scored_niches": scored, "logs": logs}


def node_select_niche(state: AgentState) -> AgentState:
    best = state["scored_niches"][0]
    logs = state.get("logs", []) + [f"Selected niche: {best['niche']} ({best['virality_score']})."]
    return {**state, "selected_niche": best, "logs": logs}


def node_generate_post(state: AgentState) -> AgentState:
    post = generate_post_content(state["selected_niche"])
    logs = state.get("logs", []) + ["Generated post package (caption + image prompt + hashtags)."]
    return {**state, "generated_post": post, "logs": logs}


def node_send_hitl_request(state: AgentState) -> AgentState:
    channel = state.get("approval_channel", os.getenv("APPROVAL_CHANNEL", "email"))
    token = uuid.uuid4().hex[:8]
    post = state["generated_post"]
    niche = state["selected_niche"]

    body = (
        f"Approval needed for today's Instagram post\n\n"
        f"Token: {token}\n"
        f"Niche: {niche['niche']}\n"
        f"Virality Score: {niche['virality_score']}\n\n"
        f"Caption:\n{post['caption']}\n\n"
        f"Image Prompt:\n{post['image_prompt']}\n\n"
        f"Hashtags:\n{post['hashtags']}\n\n"
        "Reply APPROVE or REJECT in your workflow system."
    )

    try:
        if channel == "email":
            send_email_approval(subject="[HITL] Instagram Post Approval Required", body=body)
            dispatch_log = f"Sent HITL request via {channel}. Token={token}."
        elif channel == "whatsapp":
            send_whatsapp_approval(message=body)
            dispatch_log = f"Sent HITL request via {channel}. Token={token}."
        else:
            raise ValueError("approval_channel must be 'email' or 'whatsapp'.")
    except Exception as exc:
        dispatch_log = f"HITL dispatch fallback (dry mode) due to: {exc}"

    logs = state.get("logs", []) + [dispatch_log]
    return {
        **state,
        "approval_channel": channel,
        "approval_token": token,
        "approval_status": "pending",
        "logs": logs,
    }


def node_wait_for_human(state: AgentState) -> AgentState:
    approved = state.get("human_approved")
    if approved is None:
        logs = state.get("logs", []) + [
            "No human decision in state. Use --approve yes/no or update state from webhook callback."
        ]
        return {**state, "approval_status": "pending", "logs": logs}

    status: Literal["approved", "rejected"] = "approved" if approved else "rejected"
    logs = state.get("logs", []) + [f"Human decision received: {status}."]
    return {**state, "approval_status": status, "logs": logs}


def approval_router(state: AgentState) -> str:
    status = state.get("approval_status", "pending")
    if status == "approved":
        return "publish"
    if status == "rejected":
        return "end"
    return "end"


def node_publish(state: AgentState) -> AgentState:
    post = state["generated_post"]
    caption = f"{post['caption']}\n\n{post['hashtags']}"

    publisher = InstagramPublisher(
        business_account_id=os.getenv("IG_BUSINESS_ACCOUNT_ID", "demo_account"),
        access_token=os.getenv("IG_ACCESS_TOKEN", "demo_token"),
        dry_run=True,
    )
    result = publisher.publish(caption=caption, image_url="https://picsum.photos/1080")

    logs = state.get("logs", []) + ["Published Instagram post (or dry-run simulated publish)."]
    return {**state, "publish_result": result, "logs": logs}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("fetch_and_score", node_fetch_and_score)
    graph.add_node("select_niche", node_select_niche)
    graph.add_node("generate_post", node_generate_post)
    graph.add_node("send_hitl", node_send_hitl_request)
    graph.add_node("wait_for_human", node_wait_for_human)
    graph.add_node("publish", node_publish)

    graph.add_edge(START, "fetch_and_score")
    graph.add_edge("fetch_and_score", "select_niche")
    graph.add_edge("select_niche", "generate_post")
    graph.add_edge("generate_post", "send_hitl")
    graph.add_edge("send_hitl", "wait_for_human")
    graph.add_conditional_edges(
        "wait_for_human",
        approval_router,
        {
            "publish": "publish",
            "end": END,
        },
    )
    graph.add_edge("publish", END)

    return graph.compile()


def run_agent(approval_channel: str = "email", human_approved: Optional[bool] = None) -> AgentState:
    app = build_graph()
    initial_state: AgentState = {
        "approval_channel": approval_channel,
        "human_approved": human_approved,
        "logs": [],
    }
    return app.invoke(initial_state)
