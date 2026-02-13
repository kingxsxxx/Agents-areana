from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Agent, AgentType, Debate, Score, Speech
from ..utils.logger import logger


class ScoreManager:
    @staticmethod
    async def generate_scores(debate_id: int, session: AsyncSession) -> dict:
        debate = (await session.execute(select(Debate).where(Debate.id == debate_id))).scalar_one_or_none()
        if debate is None:
            raise ValueError(f"Debate {debate_id} not found")

        agents = (
            await session.execute(select(Agent).where(Agent.debate_id == debate_id))
        ).scalars().all()
        speeches = (
            await session.execute(select(Speech).where(Speech.debate_id == debate_id))
        ).scalars().all()

        judges = [a for a in agents if a.agent_type == AgentType.JUDGE]
        if not judges:
            judges = [Agent(id=0, debate_id=debate_id, agent_type=AgentType.JUDGE, name="system", ai_model="system")]

        pro_count = sum(1 for s in speeches if getattr(s, "side", None) and s.side.value == "pro")
        con_count = sum(1 for s in speeches if getattr(s, "side", None) and s.side.value == "con")
        total_count = max(1, pro_count + con_count)
        base_pro = round(60 + 40 * pro_count / total_count)
        base_con = round(60 + 40 * con_count / total_count)

        created = []
        for judge in judges:
            score = Score(
                debate_id=debate_id,
                judge_id=judge.id,
                pro_score=base_pro,
                con_score=base_con,
                comments="Auto-generated score",
            )
            session.add(score)
            created.append(score)

        await session.commit()

        pro_total = sum(s.pro_score for s in created)
        con_total = sum(s.con_score for s in created)
        pro_avg = round(pro_total / len(created), 2)
        con_avg = round(con_total / len(created), 2)
        winner = "pro" if pro_avg > con_avg else "con" if con_avg > pro_avg else "draw"

        result = {
            "scores": [
                {
                    "judge_id": s.judge_id,
                    "pro_score": s.pro_score,
                    "con_score": s.con_score,
                    "comments": s.comments,
                }
                for s in created
            ],
            "pro_total": pro_total,
            "con_total": con_total,
            "pro_avg": pro_avg,
            "con_avg": con_avg,
            "winner": winner,
            "judge_count": len(created),
        }
        logger.info(f"Generated scores for debate {debate_id}")
        return result


async def generate_debate_scores(debate_id: int, session: AsyncSession) -> dict:
    return await ScoreManager.generate_scores(debate_id, session)
