"""
Reflexion Executor
支持自我反思和改进的执行器
"""

import json
import logging
from datetime import datetime

import httpx

from app.models.agent_models import AgentResult, Evaluation, Reflection

logger = logging.getLogger(__name__)


class ReflexionExecutor:
    """
    Reflexion 执行器 - 支持自我反思和改进
    基于 Reflexion 论文的实现

    流程:
    1. 尝试执行任务
    2. 评估结果质量
    3. 如果不满意，反思问题并重试
    4. 重复直到结果满意或达到最大尝试次数
    """

    def __init__(self, llm_client_url: str = "http://model-adapter:8005"):
        self.llm_client_url = llm_client_url
        self.max_trials = 3
        self.satisfaction_threshold = 0.7

    async def execute(
        self,
        task: str,
        context: dict = None,
        max_trials: int = None
    ) -> AgentResult:
        """
        带反思的执行

        Args:
            task: 任务描述
            context: 上下文
            max_trials: 最大尝试次数

        Returns:
            AgentResult: 最终结果
        """
        start_time = datetime.utcnow()
        max_trials = max_trials or self.max_trials

        history = []
        best_result = None
        best_score = 0.0

        logger.info(f"Reflexion started: {task} (max_trials={max_trials})")

        for trial in range(max_trials):
            logger.info(f"Trial {trial + 1}/{max_trials}")

            # Step 1: 尝试执行任务
            attempt_result = await self._attempt_task(task, history, context)

            # Step 2: 评估结果
            evaluation = await self._evaluate_result(task, attempt_result, context)

            logger.info(f"Trial {trial + 1} score: {evaluation.score:.2f}")

            # 更新最佳结果
            if evaluation.score > best_score:
                best_score = evaluation.score
                best_result = attempt_result

            # Step 3: 检查是否满意
            if evaluation.is_satisfactory:
                logger.info(f"Satisfactory result achieved in trial {trial + 1}")
                duration = (datetime.utcnow() - start_time).total_seconds()

                return AgentResult(
                    answer=attempt_result,
                    plan=None,
                    step_results=[],
                    success=True,
                    duration=duration,
                    metadata={
                        "trials": trial + 1,
                        "final_score": evaluation.score,
                        "reflections": history
                    }
                )

            # Step 4: 反思并记录
            if trial < max_trials - 1:  # 不是最后一次尝试
                reflection = await self._reflect(
                    task, attempt_result, evaluation, context
                )

                history.append({
                    "trial": trial + 1,
                    "result": attempt_result,
                    "evaluation": {
                        "score": evaluation.score,
                        "issues": evaluation.issues
                    },
                    "reflection": reflection
                })

                logger.info(f"Reflection: {reflection.insight}")

        # 所有尝试都不满意，返回最好的结果
        logger.warning(f"Max trials reached. Best score: {best_score:.2f}")
        duration = (datetime.utcnow() - start_time).total_seconds()

        return AgentResult(
            answer=best_result or "无法生成满意的答案",
            plan=None,
            step_results=[],
            success=False,
            duration=duration,
            metadata={
                "trials": max_trials,
                "best_score": best_score,
                "reflections": history
            },
            error="未达到满意度阈值"
        )

    async def _attempt_task(
        self,
        task: str,
        history: list[dict],
        context: dict = None
    ) -> str:
        """
        尝试执行任务

        Args:
            task: 任务描述
            history: 之前的尝试历史
            context: 上下文

        Returns:
            str: 执行结果
        """
        # 构建 prompt
        history_str = ""
        if history:
            history_str = "\n\n历史尝试和反思:\n"
            for h in history:
                history_str += f"\n尝试 {h['trial']}:\n"
                history_str += f"结果: {h['result'][:200]}...\n"
                history_str += f"问题: {', '.join(h['evaluation']['issues'])}\n"
                history_str += f"改进建议: {h['reflection'].suggestions}\n"

        context_str = f"\n\n上下文信息:\n{json.dumps(context, ensure_ascii=False)}" if context else ""

        prompt = f"""请完成以下任务:

任务: {task}
{context_str}
{history_str}

{'请根据以上历史尝试和反思，避免之前的错误，生成更好的答案。' if history else '请给出最佳答案。'}
"""

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"{self.llm_client_url}/api/v1/chat/completions",
                    json={
                        "model": "gpt-4-turbo-preview",
                        "messages": [
                            {"role": "system", "content": "你是一个善于学习和改进的助手。请仔细分析任务要求和历史反思，给出高质量的答案。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2000
                    }
                )
                response.raise_for_status()

                result = response.json()
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Task attempt failed: {e}")
            return f"执行失败: {str(e)}"

    async def _evaluate_result(
        self,
        task: str,
        result: str,
        context: dict = None
    ) -> Evaluation:
        """
        评估结果质量

        Returns:
            Evaluation: 评估结果
        """
        context_str = f"\n\n上下文: {json.dumps(context, ensure_ascii=False)}" if context else ""

        prompt = f"""请评估以下答案的质量:

任务: {task}
{context_str}

答案:
{result}

请从以下维度评估:
1. 正确性: 答案是否准确、事实正确
2. 完整性: 是否充分回答了问题的所有方面
3. 相关性: 是否紧扣主题，没有偏离
4. 清晰度: 表达是否清晰、逻辑是否连贯
5. 实用性: 答案是否有实际价值

返回 JSON 格式:
{{
    "is_satisfactory": true/false,
    "score": 0.0-1.0,
    "issues": ["问题1", "问题2"],
    "strengths": ["优点1", "优点2"]
}}
"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.llm_client_url}/api/v1/chat/completions",
                    json={
                        "model": "gpt-4-turbo-preview",
                        "messages": [
                            {"role": "system", "content": "你是一个严格的质量评估专家。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 500
                    }
                )
                response.raise_for_status()

                resp_data = response.json()
                content = resp_data["choices"][0]["message"]["content"]

                # 清理 JSON
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                eval_data = json.loads(content)

                return Evaluation(
                    is_satisfactory=eval_data.get("is_satisfactory", False) or eval_data.get("score", 0.0) >= self.satisfaction_threshold,
                    score=eval_data.get("score", 0.0),
                    issues=eval_data.get("issues", []),
                    strengths=eval_data.get("strengths", [])
                )

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            # 降级：简单评估
            return Evaluation(
                is_satisfactory=False,
                score=0.5,
                issues=["评估失败"],
                strengths=[]
            )

    async def _reflect(
        self,
        task: str,
        result: str,
        evaluation: Evaluation,
        context: dict = None
    ) -> Reflection:
        """
        生成反思

        Returns:
            Reflection: 反思结果
        """
        context_str = f"\n上下文: {json.dumps(context, ensure_ascii=False)}" if context else ""

        prompt = f"""请分析以下尝试的失败原因，并提出改进建议。

任务: {task}
{context_str}

尝试的答案:
{result}

评估结果:
- 得分: {evaluation.score:.2f}
- 存在问题: {', '.join(evaluation.issues)}
- 优点: {', '.join(evaluation.strengths)}

请深入分析:
1. 为什么这个答案不够好？
2. 具体哪些地方需要改进？
3. 下次尝试应该如何做得更好？

返回 JSON 格式:
{{
    "root_causes": ["根本原因1", "根本原因2"],
    "suggestions": ["改进建议1", "改进建议2"],
    "insight": "关键洞察"
}}
"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.llm_client_url}/api/v1/chat/completions",
                    json={
                        "model": "gpt-4-turbo-preview",
                        "messages": [
                            {"role": "system", "content": "你是一个善于反思和分析的专家，能够深入分析失败原因并提出有建设性的改进建议。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.5,
                        "max_tokens": 800
                    }
                )
                response.raise_for_status()

                resp_data = response.json()
                content = resp_data["choices"][0]["message"]["content"]

                # 清理 JSON
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                reflect_data = json.loads(content)

                return Reflection(
                    root_causes=reflect_data.get("root_causes", []),
                    suggestions=reflect_data.get("suggestions", []),
                    insight=reflect_data.get("insight", "")
                )

        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            # 降级
            return Reflection(
                root_causes=["反思失败"],
                suggestions=["请重新尝试"],
                insight="无法生成详细反思"
            )
