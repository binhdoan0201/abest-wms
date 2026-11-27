#!/usr/bin/env python3
"""Script sinh bcrypt hash cho mật khẩu người dùng demo.

Dùng để sinh password_hash trong database/seeds/03_users_demo.sql.
"""

import sys

import bcrypt


def hash_password(password: str) -> str:
    """Sinh chuỗi bcrypt hash từ mật khẩu plain-text."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def main() -> int:
    """Hàm thực thi chính."""
    password = sys.argv[1] if len(sys.argv) > 1 else "Demo@123456"
    hashed = hash_password(password)
    print(hashed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
