import uuid

import pytest

from proofhire_api.security.jwt import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_oauth_state_token,
    create_refresh_token,
    decode_token,
)


def test_access_token_round_trips():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_token(token, TokenType.ACCESS) == user_id


def test_refresh_token_round_trips():
    user_id = uuid.uuid4()
    token = create_refresh_token(user_id)
    assert decode_token(token, TokenType.REFRESH) == user_id


def test_oauth_state_token_round_trips():
    user_id = uuid.uuid4()
    token = create_oauth_state_token(user_id)
    assert decode_token(token, TokenType.OAUTH_STATE) == user_id


def test_wrong_token_type_is_rejected():
    user_id = uuid.uuid4()
    access = create_access_token(user_id)
    with pytest.raises(InvalidTokenError):
        decode_token(access, TokenType.REFRESH)


def test_garbage_token_is_rejected():
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-real-token", TokenType.ACCESS)
