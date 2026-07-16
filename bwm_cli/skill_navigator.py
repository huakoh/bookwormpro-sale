"""
技能导航器 — Python 实现

根据用户意图智能推荐技能组合。

Usage:
    from bwm_cli.skill_navigator import navigate
    result = navigate("我想搭建一个SaaS产品")
    # result -> {"scenario": "搭建SaaS", "skills": [...], "path": [...]}
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 场景路由表
SCENARIO_ROUTES = {
    "SaaS产品": {
        "skills": ["product-manager-expert", "architect-expert", "frontend-design",
                    "backend-builder", "devops-expert", "security-expert"],
        "keywords": ["SaaS", "搭建产品", "创业项目", "web应用", "全栈"]
    },
    "数据分析": {
        "skills": ["data-analyst-expert", "ai-ml-expert", "data-science", "data-engineer-expert"],
        "keywords": ["数据分析", "数据挖掘", "机器学习", "模型训练", "报表"]
    },
    "商业计划": {
        "skills": ["business-plan-skill", "finance-advisor", "pricing-strategist",
                    "industry-research-cn", "investor-review-guide"],
        "keywords": ["商业计划", "BP", "融资", "创业计划", "市场分析"]
    },
    "部署上线": {
        "skills": ["cloud-architect", "kubernetes-specialist", "terraform-engineer",
                    "setup-deploy", "ship", "devops-expert"],
        "keywords": ["部署", "上线", "云服务", "Docker", "K8s", "AWS", "Vercel"]
    },
    "安全审计": {
        "skills": ["security-expert", "devsecops-expert", "guardian",
                    "skill-guardian", "red-teaming"],
        "keywords": ["安全", "审计", "漏洞", "渗透", "合规"]
    },
    "SEO优化": {
        "skills": ["technical-seo-expert", "programmatic-seo", "copywriter-expert",
                    "growth-hacker", "social-media-manager"],
        "keywords": ["SEO", "搜索引擎", "排名", "流量", "关键词"]
    },
    "微信小程序": {
        "skills": ["miniprogram-expert", "frontend-expert", "api-designer",
                    "mobile-expert", "backend-builder"],
        "keywords": ["小程序", "微信", "支付宝", "uni-app", "Taro"]
    },
    "团队管理": {
        "skills": ["tech-lead-mentor", "project-coordinator", "developer-expert",
                    "reviewer-expert", "customer-success-expert"],
        "keywords": ["团队", "管理", "招聘", "绩效", "OKR", "1on1"]
    },
    "AI Agent开发": {
        "skills": ["ai-ml-expert", "prompt-optimizer", "codex", "mlops",
                    "red-teaming", "agent-evaluator"],
        "keywords": ["Agent", "AI", "LLM", "RAG", "Prompt", "微调"]
    },
    "算法竞赛": {
        "skills": ["algorithm-expert", "python-pro", "developer-expert", "debugger-expert"],
        "keywords": ["算法", "LeetCode", "ACM", "竞赛", "优化"]
    },
}

# 学习路径
LEARNING_PATHS = {
    "level1": ["developer-expert", "frontend-design", "project-coordinator",
               "github", "security-expert"],
    "level2": ["architect-expert", "ai-ml-expert", "devops-expert",
               "product-manager-expert", "algorithm-expert"],
    "level3": ["kubernetes-specialist", "red-teaming", "mlops",
               "ai-philosophy-expert", "skill-guardian"],
}

# 替代方案
ALTERNATIVES = {
    "typescript-pro": ["developer-expert", "frontend-expert"],
    "kubernetes-specialist": ["cloud-native-expert", "terraform-engineer"],
    "ai-philosophy-expert": ["security-expert", "guardian"],
    "flutter-expert": ["mobile-expert", "frontend-expert"],
    "rust-engineer": ["golang-pro", "python-pro"],
}


def navigate(intent: str) -> Dict[str, Any]:
    """根据用户意图推荐技能。"""
    intent_lower = intent.lower()

    # 匹配场景
    best_match = None
    best_score = 0

    for scenario, route in SCENARIO_ROUTES.items():
        score = sum(1 for kw in route["keywords"] if kw.lower() in intent_lower)
        if score > best_score:
            best_score = score
            best_match = scenario

    if best_match and best_score > 0:
        route = SCENARIO_ROUTES[best_match]
        return {
            "scenario": best_match,
            "skills": route["skills"],
            "matched_keywords": [kw for kw in route["keywords"] if kw.lower() in intent_lower],
            "learning_path": LEARNING_PATHS.get("level1", []),
        }

    # 无匹配时返回基础路径
    return {
        "scenario": "通用任务",
        "skills": LEARNING_PATHS["level1"],
        "matched_keywords": [],
        "learning_path": LEARNING_PATHS["level1"],
    }


def get_alternative(skill: str) -> List[str]:
    """获取技能替代方案。"""
    return ALTERNATIVES.get(skill, [])


def get_learning_path(level: str = "level1") -> List[str]:
    """获取学习路径。"""
    return LEARNING_PATHS.get(level, LEARNING_PATHS["level1"])
