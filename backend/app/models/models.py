from typing import List, Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, Integer, ForeignKey, Index, UniqueConstraint
from sqlalchemy.sql import func
from pydantic import EmailStr


# ---------------------------------------------------------------------------
# Tablas de asociación (link models con table=True)
# ---------------------------------------------------------------------------

class UserRoleLink(SQLModel, table=True):
    __tablename__ = "user_roles"

    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True)
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id", primary_key=True)
    assigned_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


class RolePermissionLink(SQLModel, table=True):
    __tablename__ = "role_permissions"

    role_id: Optional[int] = Field(default=None, foreign_key="roles.id", primary_key=True)
    permission_id: Optional[int] = Field(default=None, foreign_key="permissions.id", primary_key=True)
    # "allow" (por defecto) | "deny" — una regla deny gana siempre sobre cualquier allow
    effect: str = Field(default="allow")
    # nombre de una assertion registrada en app.core.assertions; si está seteado la
    # regla es un allow condicional (otorga sólo si el predicado pasa en runtime)
    assertion: Optional[str] = Field(default=None)
    # alcance de datos del allow: "all" (default, todas las filas) | "own" (solo las
    # del usuario, comparando el atributo de propiedad) | "attribute" (las que
    # coinciden con los valores del usuario en `scope_dimension`, ver tabla user_scopes)
    scope: str = Field(default="all")
    # dimensión de user_scopes a comparar cuando scope == "attribute" (ej. "warehouse")
    scope_dimension: Optional[str] = Field(default=None)
    assigned_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


class RoleParentLink(SQLModel, table=True):
    """Jerarquía de roles (DAG multi-padre): `role_id` hereda de `parent_id`."""

    __tablename__ = "role_parents"

    role_id: Optional[int] = Field(default=None, foreign_key="roles.id", primary_key=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="roles.id", primary_key=True)


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------

class PermissionBase(SQLModel):
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    resource: str
    action: str
    is_active: bool = True


class Permission(PermissionBase, table=True):
    __tablename__ = "permissions"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now(), nullable=True),
    )
    roles: List["Role"] = Relationship(back_populates="permissions", link_model=RolePermissionLink, sa_relationship_kwargs={"lazy": "selectin"})


class PermissionCreate(PermissionBase):
    pass


class PermissionRead(PermissionBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PermissionUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------

class RoleBase(SQLModel):
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    is_active: bool = True


class Role(RoleBase, table=True):
    __tablename__ = "roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now(), nullable=True),
    )
    users: List["User"] = Relationship(back_populates="roles", link_model=UserRoleLink, sa_relationship_kwargs={"lazy": "selectin"})
    permissions: List[Permission] = Relationship(back_populates="roles", link_model=RolePermissionLink, sa_relationship_kwargs={"lazy": "selectin"})
    parents: List["Role"] = Relationship(
        back_populates="children",
        link_model=RoleParentLink,
        sa_relationship_kwargs={
            "primaryjoin": "Role.id==RoleParentLink.role_id",
            "secondaryjoin": "Role.id==RoleParentLink.parent_id",
            "lazy": "selectin",
        },
    )
    children: List["Role"] = Relationship(
        back_populates="parents",
        link_model=RoleParentLink,
        sa_relationship_kwargs={
            "primaryjoin": "Role.id==RoleParentLink.parent_id",
            "secondaryjoin": "Role.id==RoleParentLink.role_id",
        },
    )

    @property
    def parent_ids(self) -> List[int]:
        return [p.id for p in self.parents if p.id is not None]


class RoleCreate(RoleBase):
    pass


class RoleRead(RoleBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    permissions: List[PermissionRead] = []
    parent_ids: List[int] = []


class RoleUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)
    full_name: Optional[str] = None
    is_active: bool = True


class User(UserBase, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    is_superuser: bool = False
    token_version: int = Field(default=1)
    created_by: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now(), nullable=True),
    )
    roles: List[Role] = Relationship(back_populates="users", link_model=UserRoleLink, sa_relationship_kwargs={"lazy": "selectin"})


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    is_superuser: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    roles: List[RoleRead] = []


class UserUpdate(SQLModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    username: Optional[str] = None
    action: str
    resource: str
    resource_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    status: str = Field(default="success")
    before_data: Optional[str] = None
    after_data: Optional[str] = None
    subject_id: Optional[int] = None
    user_agent: Optional[str] = None
    timestamp: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


# ---------------------------------------------------------------------------
# PasswordResetToken
# ---------------------------------------------------------------------------

class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    )
    token_hash: str = Field(index=True)
    expires_at: datetime
    used: bool = Field(default=False)
    used_at: Optional[datetime] = None
    ip_requested: Optional[str] = None
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


# ---------------------------------------------------------------------------
# Scoping de datos (alcance por atributo del usuario)
# ---------------------------------------------------------------------------

class UserScope(SQLModel, table=True):
    """Valor que ubica al usuario dentro de una dimensión de alcance.

    Ej.: `(user_id=4, dimension="warehouse", value="norte")` => el usuario 4
    pertenece al depósito "norte". Una regla `role_permissions` con
    `scope="attribute"` y `scope_dimension="warehouse"` limita las filas visibles
    a las que coinciden con estos valores.
    """

    __tablename__ = "user_scopes"
    __table_args__ = (
        UniqueConstraint("user_id", "dimension", "value", name="uq_user_scope"),
        Index("ix_user_scopes_user_dimension", "user_id", "dimension"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    )
    dimension: str
    value: str


class UserScopeRead(SQLModel):
    dimension: str
    value: str


# Resolver referencias circulares
Permission.model_rebuild()
Role.model_rebuild()
User.model_rebuild()
RoleRead.model_rebuild()
UserRead.model_rebuild()
PasswordResetToken.model_rebuild()
