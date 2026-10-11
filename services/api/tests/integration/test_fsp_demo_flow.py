from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, FspLink
from app.modules.fsp import demo
from app.modules.recommendations import talent_service
from test_ranking_create import setup, certify
from test_candidate_profile import env
from test_assessment_v3_lifecycle import approved


def test_demo_file_populates_profile_ranking_and_filter_without_db_achievement(env, approved, monkeypatch):
    client, headers, ids, engine = env
    monkeypatch.setattr(demo, "active_registry", lambda: demo.load_registry())
    monkeypatch.setattr(talent_service, "active_registry", lambda: demo.load_registry())
    url, _ = setup(env)
    certify(env, 0, 18)
    certify(env, 1, 18)
    with Session(engine) as session, session.begin():
        profiles = [session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == uid)) for uid in ids[:2]]
        session.add(FspLink(candidate_id=profiles[0].id, status="linked", fsp_id="demo-fsp-002",
                            linked_at=datetime.now(timezone.utc)))
        session.add(FspLink(candidate_id=profiles[1].id, status="linked", fsp_id="not-in-file",
                            linked_at=datetime.now(timezone.utc)))
        pids = [p.id for p in profiles]
    profile = client.get("/me/candidate-profile", headers=headers[0]).json()
    assert profile["fspSource"] == "synthetic-demo-not-fsp"
    assert profile["fspAchievements"][0]["recordId"] == "demo-result-002"
    snapshot = client.post(url, headers=headers[2])
    assert snapshot.status_code == 200, snapshot.text
    data = snapshot.json()
    assert [i["candidate"]["id"] for i in data["items"]] == pids
    assert data["items"][0]["components"]["fspBonus"] > 0
    assert data["items"][1]["components"]["fspBonus"] == 0
    assert "Demo FSP bonus" in data["items"][0]["reasons"][2]
    filtered = client.get(f"{url}/{data['id']}/items", headers=headers[2],
                          params={"hasFspAchievements": "true"})
    assert filtered.status_code == 200, filtered.text
    assert [i["candidate"]["id"] for i in filtered.json()["items"]] == pids[:1]
    monkeypatch.setattr(talent_service, "active_registry", lambda: {})
    assert client.get(f"{url}/{data['id']}/items", headers=headers[2],
                      params={"hasFspAchievements": "true"}).json() == filtered.json()
    assert client.get(f"{url}/{data['id']}", headers=headers[2]).json() == data
