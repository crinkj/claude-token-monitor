# Claude Code Token Monitor

macOS 메뉴바에서 Claude Code 토큰 사용량을 실시간으로 확인할 수 있는 SwiftBar 플러그인입니다.

```
⚡ 128.5K/3.6M
```

## Features

- **실시간 토큰 추적** — 세션 JSONL에서 실제 토큰 수 파싱 (input + output + cache)
- **비용 기반 모니터링** — 토큰 수 + 실제 모델별 가격으로 비용 추적
- **동적 토큰 한도** — 사용 중인 모델 믹스에 따라 토큰 한도 자동 계산
- **모델별 분류** — Opus / Sonnet / Haiku 사용량 각각 표시
- **플랜 프리셋** — Pro / Max 5x / Max 20x 자동 설정
- **색상 경고** — 70% 이상 노란색, 90% 이상 빨간색

## How It Works

### 토큰 측정 방식

1. Claude Code 응답 완료 시 `Stop` hook이 실행됩니다
2. Hook이 세션 JSONL에서 `usage` 데이터를 파싱합니다 (`input_tokens`, `output_tokens`, `cache_creation_tokens`, `cache_read_tokens`)
3. 사용 기록이 `~/.claude/dashboard/usage.json`에 타임스탬프, 모델명, 비용과 함께 저장됩니다
4. SwiftBar 플러그인이 최근 5시간(롤링 윈도우) 내 기록만 집계하여 표시합니다

### 비용 계산

| 항목 | 설명 |
|------|------|
| **비용 한도** | 플랜별 고정값 (Pro: $18, Max 5x: $35, Max 20x: $140) |
| **토큰 한도** | `비용 한도 ÷ 실제 토큰당 비용`으로 동적 계산 |
| **토큰당 비용** | 실제 사용된 모델 믹스 기반 (Opus/Sonnet/Haiku 가격 차이 반영) |

> **참고:** 카운트다운 타이머는 의도적으로 제외했습니다. Anthropic의 실제 레이트 리밋 메커니즘을 정확히 알 수 없어, 부정확한 시간을 표시하는 것보다 사용량 자체에 집중합니다.

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/crinkj/claude-token-monitor/main/install.sh | bash
```

플랜을 지정해서 설치:

```bash
# Pro
curl -fsSL https://raw.githubusercontent.com/crinkj/claude-token-monitor/main/install.sh | bash -s -- pro

# Max 5x
curl -fsSL https://raw.githubusercontent.com/crinkj/claude-token-monitor/main/install.sh | bash -s -- max_5x

# Max 20x
curl -fsSL https://raw.githubusercontent.com/crinkj/claude-token-monitor/main/install.sh | bash -s -- max_20x
```

## Manual Install

```bash
git clone https://github.com/crinkj/claude-token-monitor.git
cd claude-token-monitor
./install.sh
```

## Configuration

`~/.claude/dashboard/config.json`:

```json
{
  "plan": "pro"
}
```

플랜 프리셋으로 자동 설정되지만, 직접 오버라이드할 수도 있습니다:

```json
{
  "plan": "pro",
  "costLimit": 18.0,
  "windowHours": 5
}
```

| 옵션 | 설명 | Pro | Max 5x | Max 20x |
|------|------|-----|--------|---------|
| `costLimit` | 윈도우당 비용 한도 ($) | 18 | 35 | 140 |
| `messageLimit` | 메시지 한도 | 250 | 1,000 | 2,000 |
| `windowHours` | 롤링 윈도우 (시간) | 5 | 5 | 5 |

## Menu Bar

```
⚡ 128.5K/3.6M          일반 사용
⚠️ 3.4M/3.6M            90% 이상 경고
```

드롭다운:
```
████████████░░░░░░░░ 64.2%
Tokens:   128.5K / 3.6M   (64.2%)
Cost:      $5.40 / $18.00  (30.0%)
Messages:    45  / 250      (18.0%)

Model breakdown:
  Opus:   $3.20 (25.0K)
  Sonnet: $2.20 (103.5K)
```

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/crinkj/claude-token-monitor/main/uninstall.sh | bash
```

또는:

```bash
git clone https://github.com/crinkj/claude-token-monitor.git
cd claude-token-monitor && ./uninstall.sh
```

## License

MIT
