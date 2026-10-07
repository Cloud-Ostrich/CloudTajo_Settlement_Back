from dataclasses import dataclass

from app.Auth.security import hash_password


@dataclass(frozen=True)
class UserRecord:
    id: int
    name: str
    email: str
    role: str
    password_salt: bytes
    password_hash: bytes


class InMemoryUserRepository:
    """Temporary repository to replace with a users-table repository later."""

    def __init__(self) -> None:
        self._users_by_email: dict[str, UserRecord] = {}
        self._users_by_id: dict[int, UserRecord] = {}
        self._save(
            self._create_user(
                1, "홍길동", "member@example.com", "password1234", "USER"
            )
        )
        self._save(
            self._create_user(
                2, "관리자", "admin@example.com", "password1234", "ADMIN"
            )
        )
        self._save(
            self._create_user(
                3, "테스트 사용자", "test@example.com", "test1234!", "USER"
            )
        )

    @staticmethod
    def _create_user(
        user_id: int,
        name: str,
        email: str,
        password: str,
        role: str,
    ) -> UserRecord:
        password_salt, password_hash = hash_password(password)
        return UserRecord(
            id=user_id,
            name=name,
            email=email.lower(),
            role=role,
            password_salt=password_salt,
            password_hash=password_hash,
        )

    def _save(self, user: UserRecord) -> None:
        self._users_by_email[user.email] = user
        self._users_by_id[user.id] = user

    def find_by_email(self, email: str) -> UserRecord | None:
        return self._users_by_email.get(email.strip().lower())

    def find_by_id(self, user_id: int) -> UserRecord | None:
        return self._users_by_id.get(user_id)


user_repository = InMemoryUserRepository()
