"""로컬 관리자 자격 증명. UI, HTTP, 주문 DB와 독립적이다."""
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import tempfile

from kiosk.config import ADMIN_ENV_FILE

PREFIX = 'scrypt$131072$8$1'


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**17, r=8, p=1,
                            dklen=32, maxmem=256 * 1024 * 1024)
    return f'{PREFIX}${salt.hex()}${digest.hex()}'


def validate_hash(encoded):
    parts = encoded.split('$')
    if len(parts) != 6 or '$'.join(parts[:4]) != PREFIX:
        raise ValueError('Unsupported password hash')
    salt, digest = bytes.fromhex(parts[4]), bytes.fromhex(parts[5])
    if len(salt) != 16 or len(digest) != 32:
        raise ValueError('Invalid password hash')
    return salt, digest


def verify_password(password, encoded):
    salt, expected = validate_hash(encoded)
    if not isinstance(password, str) or len(password) > 128:
        return False
    actual = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**17, r=8, p=1,
                            dklen=32, maxmem=256 * 1024 * 1024)
    return hmac.compare_digest(actual, expected)


class AdminCredentials:
    def __init__(self, path=ADMIN_ENV_FILE):
        self.path = Path(path)

    def initialize(self):
        """파일이 없을 때만 최초 생성. 손상된 파일은 초기 비밀번호로 덮어쓰지 않는다."""
        if not self.path.exists():
            self._write(hash_password('1234'), initial=True, create_only=True)
        return self.read()

    def read(self):
        try:
            data = {}
            for line in self.path.read_text(encoding='utf-8').splitlines():
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                key, value = line.split('=', 1)
                if key.strip() in data:
                    raise ValueError('Duplicate key')
                data[key.strip()] = value.strip()
            validate_hash(data['ADMIN_PASSWORD_HASH'])
            if data['ADMIN_PASSWORD_INITIAL'] not in ('0', '1'):
                raise ValueError('Invalid initial flag')
            return data
        except (OSError, ValueError, KeyError) as exc:
            raise RuntimeError('관리자 설정 파일을 읽을 수 없습니다. .env.admin 파일을 확인해주세요.') from exc

    def authenticate(self, password):
        data = self.read()
        if not verify_password(password, data['ADMIN_PASSWORD_HASH']):
            raise ValueError('비밀번호가 올바르지 않습니다.')
        return data['ADMIN_PASSWORD_INITIAL'] == '1'

    def change_password(self, current, new, confirmation):
        self.authenticate(current)
        if new != confirmation:
            raise ValueError('새 비밀번호와 확인 값이 일치하지 않습니다.')
        if not 8 <= len(new) <= 128:
            raise ValueError('새 비밀번호는 8~128자로 입력해주세요.')
        if current == new:
            raise ValueError('현재와 다른 비밀번호를 입력해주세요.')
        self._write(hash_password(new), initial=False)

    def _write(self, encoded, initial, create_only=False):
        # 같은 디렉터리의 임시 파일을 교체하므로 저장 실패 시 이전 설정이 유지된다.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=self.path.name + '.', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write('# Local administrator credentials. Do not commit this file.\n')
                stream.write(f'ADMIN_PASSWORD_HASH={encoded}\nADMIN_PASSWORD_INITIAL={int(initial)}\n')
                stream.flush()
                os.fsync(stream.fileno())
            if create_only:
                try:
                    os.link(temporary, self.path)
                except FileExistsError:
                    pass
            else:
                os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)
