# Skills层 - 技能基类
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseSkill(ABC):
    """技能基类 - 组合多个 tools 完成复杂任务"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行技能"""
        pass

    def get_info(self) -> Dict[str, str]:
        """获取技能信息"""
        return {"name": self.name, "description": self.description}