"""
Chat agent sang loc benh rang mieng tu anh mau (KHONG chan doan thay bac si).

Workflow van hanh (9 buoc):
  1. Nguoi dung gui anh + mo ta trieu chung
  2. Kiem tra chat luong anh (goi lai neu khong dat)
  3. Tien xu ly anh mau
  4. Phat hien vung bat thuong bang bbox (detector, 4 lop)
  5. Phan loai tinh trang toan anh (classifier, 6 lop) + dien giai than thien
  6. Hoi them trieu chung theo nhom benh da phat hien
  7. Hop nhat ket qua anh + hoi thoai
  8. Danh gia muc do nguy co (rule-based, KHONG giao cho LLM quyet dinh)
  9. Tra loi cuoi: nhan dinh chinh + kha nang lien quan + muc do nguy co + khuyen nghi

Lop hoi thoai (dat cau hoi, dien giai, phrase cau tra loi cuoi) dung OpenAI API.
Lop triage (danh gia nguy co) la rule-based de dam bao nhat quan/an toan va
khong phu thuoc "am tinh" cua LLM - LLM chi duoc dung de DIEN DAT lai ket qua
da tinh san, khong duoc tu quyet dinh muc do nguy co.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from enum import Enum
from importlib import import_module

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # doc OPENAI_API_KEY (va cac bien khac neu co) tu file .env neu ton tai

_prep = import_module("1_dental_preprocess")
_detect = import_module("2_detect_dental_conditions")

CLASSIFIER_CLASSES = _prep.CLASSIFIER_CLASSES
VisionFindings = _detect.VisionFindings
to_human_findings = _detect.to_human_findings

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

DISCLAIMER = (
    "Day la cong cu ho tro sang loc so bo tu anh, KHONG thay the cho chan doan "
    "va dieu tri cua bac si nha khoa. Neu trieu chung keo dai hoac nang len, "
    "ban nen den kham truc tiep."
)


# --------------------------------------------------------------------------
# Muc do nguy co (rule-based)
# --------------------------------------------------------------------------


class RiskLevel(str, Enum):
    LOW = "nhe - theo doi va cham soc tai nha"
    MEDIUM = "trung binh - nen kham nha khoa som"
    HIGH = "cao - can di kham som hoac ngay"

    def rank(self) -> int:
        return {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}[self]


# Cac truong tin hieu trieu chung duoc trich xuat tu hoi thoai (structured, dung
# cho triage - KHONG dung van ban tu do de tranh sai lech quy tac an toan)
SYMPTOM_FIELDS = {
    "e_buot_lanh": "co e buot khi an/uong do lanh hay khong (bool)",
    "dau_khi_nhai": "co dau khi nhai hay khong (bool)",
    "dau_tu_phat": "co dau tu phat, khong can kich thich, hay khong (bool)",
    "chay_mau_khi_danh_rang": "co chay mau nuou khi danh rang hay khong (bool)",
    "nuou_sung": "nuou co sung ro hay khong (bool)",
    "hoi_mieng": "co hoi mieng keo dai hay khong (bool)",
    "trieu_chung_so_ngay": "trieu chung (chay mau/loet/sung) keo dai bao nhieu ngay (so nguyen, uoc luong)",
    "dau_du_doi": "co dau du doi/nang hay khong (bool)",
    "loet_nhieu_vet": "co nhieu vet loet cung luc hay chi mot vet (bool: true=nhieu vet)",
    "loet_tai_phat": "vet loet co hay tai phat thuong xuyen khong (bool)",
    "doi_mau_toan_bo": "doi mau xay ra toan bo rang hay chi mot vai rang (bool: true=toan bo)",
    "tien_su_thuoc_la_ca_phe": "co tien su hut thuoc/uong ca phe, tra dam hay khong (bool)",
    "thieu_rang_tu_nho": "thieu rang tu nho (bam sinh) hay moi mat rang gan day (bool: true=tu nho)",
    "moi_mat_rang_khong_ro_nguyen_nhan": "moi mat rang ma khong ro nguyen nhan (bool)",
    "dang_dieu_tri_nha_khoa": "hien dang nieng rang hoac dieu tri nha khoa hay khong (bool)",
}

# Nhom cau hoi theo tinh trang (mot so nhom dung chung cau hoi theo de xuat cua nguoi dung)
SYMPTOM_QUESTION_BANK: dict[str, list[str]] = {
    "Caries": [
        "Ban co bi e buot khi an hoac uong do lanh khong?",
        "Ban co dau khi nhai o vung rang do khong?",
        "Con dau la tu phat hay chi xuat hien khi an?",
    ],
    "Gingivitis_Calculus": [  # dung chung cho Gingivitis va Calculus
        "Ban co bi chay mau nuou khi danh rang khong?",
        "Nuou cua ban co dang sung khong?",
        "Ban co bi hoi mieng khong?",
        "Tinh trang nay da keo dai khoang bao nhieu ngay roi?",
    ],
    "Ulcers": [
        "Vet loet xuat hien duoc bao lau roi?",
        "Ban co thay dau rat nhieu khi an do cay/nong khong?",
        "Ban co nhieu vet loet cung luc hay chi mot vet?",
        "Tinh trang loet nay co hay tai phat khong?",
    ],
    "Tooth Discoloration": [
        "Rang bi doi mau toan bo hay chi mot vai chiec?",
        "Ban co thuong xuyen hut thuoc, uong ca phe hoac tra dam khong?",
        "Vung rang doi mau co kem theo dau khong?",
    ],
    "Hypodontia": [
        "Ban thieu rang nay tu nho hay moi mat rang gan day?",
        "Ban da tung nho rang o vi tri nay chua?",
        "Ban co dang nieng rang hoac dieu tri nha khoa khong?",
    ],
}


def _question_group_for_label(label: str) -> str:
    if label in ("Gingivitis", "Calculus"):
        return "Gingivitis_Calculus"
    return label


@dataclass
class RiskAssessment:
    overall: RiskLevel
    per_condition: dict[str, dict] = field(default_factory=dict)  # label -> {"risk":..., "rationale":[...]}


class TriageEngine:
    """Logic danh gia nguy co, thuan Python, deterministic. Day la lop AN TOAN
    cua he thong nen KHONG duoc thay bang goi LLM."""

    @staticmethod
    def assess(findings: VisionFindings, symptoms: dict) -> RiskAssessment:
        per_condition: dict[str, dict] = {}
        flagged_labels = [c.label for c in findings.flagged()]

        for c in findings.flagged():
            risk, rationale = TriageEngine._assess_condition(c.label, symptoms)
            per_condition[c.label] = {"risk": risk, "rationale": rationale}

        overall = RiskLevel.LOW
        if per_condition:
            overall = max((v["risk"] for v in per_condition.values()), key=lambda r: r.rank())

        # ton thuong lan rong: >=3 nhom benh cung duoc phat hien -> tang 1 muc
        if len(flagged_labels) >= 3 and overall.rank() < RiskLevel.HIGH.rank():
            overall = RiskLevel(list(RiskLevel)[overall.rank() + 1])

        return RiskAssessment(overall=overall, per_condition=per_condition)

    @staticmethod
    def _assess_condition(label: str, s: dict) -> tuple[RiskLevel, list[str]]:
        rationale: list[str] = []
        risk = RiskLevel.LOW

        if label == "Caries":
            if s.get("dau_tu_phat"):
                risk = RiskLevel.HIGH
                rationale.append("dau tu phat co the la dau tuy, can kham som")
            elif s.get("e_buot_lanh") or s.get("dau_khi_nhai"):
                risk = RiskLevel.MEDIUM
                rationale.append("co e buot/dau khi nhai, sau rang co the da vao ngan sau")

        elif label in ("Gingivitis", "Calculus"):
            so_ngay = s.get("trieu_chung_so_ngay") or 0
            if s.get("nuou_sung") and s.get("dau_du_doi"):
                risk = RiskLevel.HIGH
                rationale.append("nuou sung ro kem dau du doi")
            elif s.get("chay_mau_khi_danh_rang") and (s.get("hoi_mieng") or so_ngay >= 14):
                risk = RiskLevel.MEDIUM
                rationale.append("chay mau nuou keo dai kem hoi mieng, kha nang viem nuou/nha chu som")
            elif s.get("chay_mau_khi_danh_rang") or s.get("nuou_sung"):
                risk = RiskLevel.MEDIUM
                rationale.append("co dau hieu viem nuou/cao rang can theo doi va lam sach")

        elif label == "Ulcers":
            so_ngay = s.get("trieu_chung_so_ngay") or 0
            if so_ngay > 14 and s.get("dau_du_doi"):
                risk = RiskLevel.HIGH
                rationale.append("vet loet keo dai hon 2 tuan kem dau nhieu")
            elif so_ngay > 14 or s.get("loet_tai_phat"):
                risk = RiskLevel.MEDIUM
                rationale.append("vet loet keo dai hoac tai phat thuong xuyen, nen kham de loai tru nguyen nhan khac")

        elif label == "Tooth Discoloration":
            if s.get("dau_du_doi"):
                risk = RiskLevel.MEDIUM
                rationale.append("doi mau rang kem dau, co the lien quan toi tuy rang")
            else:
                rationale.append("doi mau khong kem dau, uu tien theo doi/tay trang tham my")

        elif label == "Hypodontia":
            if s.get("moi_mat_rang_khong_ro_nguyen_nhan"):
                risk = RiskLevel.MEDIUM
                rationale.append("moi mat rang khong ro nguyen nhan can kham de xac dinh nguyen nhan")
            elif s.get("thieu_rang_tu_nho"):
                rationale.append("thieu rang bam sinh, phu hop theo doi dinh ky/ke hoach dieu tri hien tai")

        if s.get("dau_du_doi") and risk.rank() < RiskLevel.MEDIUM.rank():
            risk = RiskLevel.MEDIUM
            rationale.append("co dau du doi noi chung")

        return risk, rationale


# --------------------------------------------------------------------------
# Chat agent
# --------------------------------------------------------------------------


@dataclass
class SessionState:
    session_id: str
    findings: VisionFindings
    symptoms: dict = field(default_factory=dict)
    raw_notes: list[str] = field(default_factory=list)
    question_queue: list[tuple[str, str]] = field(default_factory=list)  # (group, question)
    asked_log: list[tuple[str, str]] = field(default_factory=list)  # (question, answer)


class DentalScreeningAgent:
    def __init__(self, detector, classifier, api_key: str | None = None, model: str = OPENAI_MODEL):
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Thieu OPENAI_API_KEY. Dat bien moi truong OPENAI_API_KEY truoc khi khoi tao "
                "DentalScreeningAgent (lop hoi thoai/dien giai cua agent dung OpenAI API)."
            )
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.detector = detector
        self.classifier = classifier
        self.sessions: dict[str, SessionState] = {}

    # -- Buoc 1-5: nhan anh, kiem tra chat luong, tien xu ly, detect, classify --

    def start_session(self, session_id: str, image_path: str, user_text: str = "") -> str:
        try:
            findings = _detect.run_full_pipeline(image_path)
        except ValueError as quality_error:
            return f"{quality_error}\n\nBan vui long chup lai anh ro net, du sang va gui lai giup minh nhe."

        session = SessionState(session_id=session_id, findings=findings)
        session.question_queue = self._build_question_queue(findings)
        self.sessions[session_id] = session

        if user_text.strip():
            session.raw_notes.append(user_text)
            self._extract_symptoms(session, user_text)

        findings_text = "\n".join(to_human_findings(findings))
        next_q = self.next_question(session_id)
        if next_q:
            return f"{findings_text}\n\n{next_q}"
        return f"{findings_text}\n\n{self.finalize(session_id)}"

    def _build_question_queue(self, findings: VisionFindings) -> list[tuple[str, str]]:
        queue: list[tuple[str, str]] = []
        seen_groups: set[str] = set()
        for c in findings.flagged():
            group = _question_group_for_label(c.label)
            if group in seen_groups:
                continue
            seen_groups.add(group)
            for q in SYMPTOM_QUESTION_BANK.get(group, []):
                queue.append((group, q))
        return queue

    # -- Buoc 6: hoi them trieu chung --

    def next_question(self, session_id: str) -> str | None:
        session = self.sessions[session_id]
        if not session.question_queue:
            return None
        _, question = session.question_queue[0]
        return self._phrase_question(session, question)

    def _phrase_question(self, session: SessionState, question: str) -> str:
        system = (
            "Ban la tro ly sang loc nha khoa, noi tieng Viet, than thien va ngan gon. "
            "Nhiem vu duy nhat cua ban trong luot nay la dien dat lai CHINH XAC noi dung "
            "cau hoi duoc giao, khong them cau hoi moi, khong dua ra chan doan hay ket luan y khoa."
        )
        user = f"Hay dien dat lai cau hoi sau cho tu nhien, giu nguyen y nghia: \"{question}\""
        try:
            return self._chat(system, user)
        except Exception:
            return question  # fallback: hoi nguyen van neu goi API loi

    # -- Buoc 7: hop nhat anh + hoi thoai --

    def submit_answer(self, session_id: str, answer_text: str) -> str:
        session = self.sessions[session_id]
        if session.question_queue:
            _, question = session.question_queue.pop(0)
            session.asked_log.append((question, answer_text))
        session.raw_notes.append(answer_text)
        self._extract_symptoms(session, answer_text)

        next_q = self.next_question(session_id)
        if next_q:
            return next_q
        return self.finalize(session_id)

    def _extract_symptoms(self, session: SessionState, free_text: str) -> None:
        schema_desc = "\n".join(f"- {k}: {v}" for k, v in SYMPTOM_FIELDS.items())
        system = (
            "Ban trich xuat tin hieu trieu chung tu cau tra loi cua nguoi dung thanh JSON. "
            "CHI dien cac truong ma van ban NEU RO; neu khong de cap, bo qua truong do "
            "(dung dien gia dinh). Tra ve DUY NHAT mot JSON object phang, khong giai thich them."
        )
        user = f"Danh sach truong hop le:\n{schema_desc}\n\nCau tra loi cua nguoi dung:\n\"{free_text}\""
        try:
            raw = self._chat(system, user, json_mode=True)
            extracted = json.loads(raw)
        except Exception:
            return  # khong trich xuat duoc thi giu nguyen trieu chung da co, khong chan luong hoi thoai

        for key, value in extracted.items():
            if key in SYMPTOM_FIELDS and value is not None:
                session.symptoms[key] = value

    # -- Buoc 8-9: danh gia nguy co + tra loi cuoi cung --

    def finalize(self, session_id: str) -> str:
        session = self.sessions[session_id]
        assessment = TriageEngine.assess(session.findings, session.symptoms)

        facts = {
            "phat_hien_tu_anh": [
                {"tinh_trang": c.label, "do_tin_cay": round(c.confidence, 2), "co_vi_tri_cu_the": bool(c.bboxes)}
                for c in session.findings.flagged()
            ],
            "danh_gia_nguy_co": {
                "tong_the": assessment.overall.value,
                "chi_tiet": {
                    label: {"muc_do": v["risk"].value, "ly_do": v["rationale"]}
                    for label, v in assessment.per_condition.items()
                },
            },
        }

        system = (
            "Ban la tro ly sang loc nha khoa noi tieng Viet. Hay viet PHAN HOI CUOI CUNG gom dung "
            "4 phan theo thu tu: (1) nhan dinh chinh, (2) cac kha nang lien quan, (3) muc do nguy co, "
            "(4) khuyen nghi hanh dong. CHI duoc dung du kien trong JSON du lieu duoc cung cap, KHONG "
            "duoc tu suy dien them chan doan, KHONG doi muc do nguy co da duoc tinh san. Giong van "
            "gan gui, ro rang, khong dung thuat ngu ky thuat model (vd 'confidence', 'class')."
        )
        user = f"Du lieu da phan tich (JSON):\n{json.dumps(facts, ensure_ascii=False, indent=2)}"
        try:
            body = self._chat(system, user)
        except Exception:
            body = self._fallback_summary(facts)

        return f"{body}\n\n{DISCLAIMER}"

    def _fallback_summary(self, facts: dict) -> str:
        lines = ["Nhan dinh chinh va cac kha nang lien quan:"]
        for item in facts["phat_hien_tu_anh"]:
            lines.append(f"- {item['tinh_trang']} (do tin cay {item['do_tin_cay']:.0%})")
        lines.append(f"\nMuc do nguy co tong the: {facts['danh_gia_nguy_co']['tong_the']}")
        lines.append("Khuyen nghi: ban nen dat lich kham nha khoa de duoc danh gia chinh xac.")
        return "\n".join(lines)

    # -- OpenAI helper --

    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.3,
            response_format={"type": "json_object"} if json_mode else None,
        )
        return response.choices[0].message.content


# --------------------------------------------------------------------------
# Demo CLI
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Dung: python 5_chatbot_dental_agent.py <duong_dan_anh>")
        sys.exit(1)

    config = _detect.load_config()
    detector = _detect.DentalDetector(config["detector_weights"], config.get("detector_conf_threshold", 0.35))
    classifier = _detect.DentalClassifier(config["classifier_checkpoint"])
    agent = DentalScreeningAgent(detector, classifier)

    initial_text = input("Mo ta trieu chung ban dau (co the de trong): ")
    reply = agent.start_session("cli-session", sys.argv[1], initial_text)
    print(f"\nAgent: {reply}\n")

    session = agent.sessions["cli-session"]
    while session.question_queue:
        answer = input("Ban: ")
        reply = agent.submit_answer("cli-session", answer)
        print(f"\nAgent: {reply}\n")
