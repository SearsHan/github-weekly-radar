#!/usr/bin/env python3
"""One explicit credential check; daily runs never call it for cached projects."""
import json
import os

import requests
from validate_data import require


ERROR_REASONS = {
    'insufficient_quota': 'API 额度不足或账单限制',
    'credit_balance_exhausted': 'API 预付余额已耗尽',
    'organization_usage_limit_exceeded': '组织 API 用量上限已达到',
    'organization_spend_limit_exceeded': '组织 API 支出上限已达到',
    'project_spend_limit_exceeded': '项目 API 支出上限已达到',
    'rate_limit_exceeded': '请求或 Token 速率超过限制',
    'rate_limit_error': '请求速率超过限制',
    'slow_down': '请求速率增长过快',
    'invalid_api_key': 'API 密钥无效',
    'model_not_found': '模型不存在或无访问权限',
}


def failure_reason(response):
    # Never log response text, error messages, headers, or credentials.
    try:
        error = response.json().get('error', {})
        for field in ('code', 'type'):
            value = error.get(field)
            if isinstance(value, str) and value in ERROR_REASONS:
                return f'{value}（{ERROR_REASONS[value]}）'
    except (ValueError, TypeError, AttributeError):
        pass
    return '未识别错误类型'


def main():
    key = os.getenv('OPENAI_API_KEY', '').strip()
    require(bool(key), 'Actions 中缺少 OPENAI_API_KEY repository secret')
    model = os.getenv('OPENAI_MODEL') or 'gpt-4.1-mini'
    response = requests.post('https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={'model': model, 'messages': [{'role': 'user', 'content': 'Return the JSON object with ok equal to true.'}],
              'max_completion_tokens': 64,
              'response_format': {'type': 'json_schema', 'json_schema': {'name': 'credential_check', 'strict': True,
                  'schema': {'type': 'object', 'properties': {'ok': {'type': 'boolean'}},
                             'required': ['ok'], 'additionalProperties': False}}}}, timeout=45)
    if not response.ok:
        raise ValueError(f'模型验证失败：HTTP {response.status_code}；{failure_reason(response)}；未更新网站数据')
    choice = response.json()['choices'][0]
    require(choice.get('finish_reason') == 'stop' and not choice['message'].get('refusal'), '模型响应未完成')
    require(json.loads(choice['message']['content']) == {'ok': True}, 'Structured Outputs 验证失败')
    print(f'模型连接与 Structured Outputs 已验证：{model}')


if __name__ == '__main__':
    main()
