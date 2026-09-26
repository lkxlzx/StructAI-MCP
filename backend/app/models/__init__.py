"""All 49 ORM models of the StructAI persistence layer.

Importing this package is what populates ``Base.metadata``; ``create_all``,
Alembic autogenerate and the seeder all rely on it.

Table map (V2.1 §4):

======================  ===========================================================
module                  tables
======================  ===========================================================
``identity``            users, roles, permissions, user_roles, role_permissions,
                        sessions
``settings``            system_configs, security_configs, service_configs,
                        backup_configs, cleanup_configs
``mcp``                 mcp_servers, mcp_clients, mcp_client_credentials
``midas``               adapters, midas_clients
``ai_models``           model_providers, models
``registry``            tools, tool_interfaces, schemas, capabilities,
                        capability_interfaces
``tasks``               tasks, task_events
``logs``                system_logs, audit_logs
``data_management``     backups, data_exports, data_imports
``projects``            projects, reports
``assistant``           assistant_* (14)
``knowledge``           code_standards, code_clauses, load_parameter_library
======================  ===========================================================
"""

from app.db.base import Base
from app.models.ai_models import AiModel, ModelProvider
from app.models.assistant import (
    AssistantCommand,
    AssistantDrawingObject,
    AssistantDrawingSetting,
    AssistantDrawingTask,
    AssistantExample,
    AssistantFile,
    AssistantHistory,
    AssistantIntent,
    AssistantMessage,
    AssistantOutput,
    AssistantPlan,
    AssistantPlanStep,
    AssistantSession,
    AssistantTemplate,
)
from app.models.data_management import Backup, DataExport, DataImport
from app.models.identity import Permission, Role, RolePermission, User, UserRole, UserSession
from app.models.knowledge import CodeClause, CodeStandard, LoadParameterLibrary
from app.models.logs import AuditLog, SystemLog
from app.models.mcp import McpClient, McpClientCredential, McpServer
from app.models.midas import Adapter, MidasClient
from app.models.projects import Project, Report
from app.models.registry import Capability, CapabilityInterface, Schema, Tool, ToolInterface
from app.models.settings import (
    BackupConfig,
    CleanupConfig,
    SecurityConfig,
    ServiceConfig,
    SystemConfig,
)
from app.models.tasks import Task, TaskEvent

__all__ = [
    "Base",
    # identity (6)
    "User",
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "UserSession",
    # settings (5)
    "SystemConfig",
    "SecurityConfig",
    "ServiceConfig",
    "BackupConfig",
    "CleanupConfig",
    # mcp (3)
    "McpServer",
    "McpClient",
    "McpClientCredential",
    # midas (2)
    "Adapter",
    "MidasClient",
    # ai_models (2)
    "ModelProvider",
    "AiModel",
    # registry (5)
    "Tool",
    "ToolInterface",
    "Schema",
    "Capability",
    "CapabilityInterface",
    # tasks (2)
    "Task",
    "TaskEvent",
    # logs (2)
    "SystemLog",
    "AuditLog",
    # data_management (3)
    "Backup",
    "DataExport",
    "DataImport",
    # projects (2)
    "Project",
    "Report",
    # assistant (14)
    "AssistantFile",
    "AssistantSession",
    "AssistantMessage",
    "AssistantIntent",
    "AssistantPlan",
    "AssistantPlanStep",
    "AssistantOutput",
    "AssistantDrawingTask",
    "AssistantDrawingObject",
    "AssistantDrawingSetting",
    "AssistantTemplate",
    "AssistantExample",
    "AssistantHistory",
    "AssistantCommand",
    # knowledge (3)
    "CodeStandard",
    "CodeClause",
    "LoadParameterLibrary",
]

#: Number of mapped tables — must equal the 49 of 总纲 §6.1 / V2.1 §3.5.
TABLE_COUNT = len(Base.metadata.tables)
