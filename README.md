# Claude Code Token Monitor

macOS 메뉴바에서 Claude Code 토큰 사용량과 리셋 카운트다운을 실시간으로 확인할 수 있는 SwiftBar 플러그인입니다.

```
⚡ 128.5K/200.0K · ⏱ 3h45m12s
```

## Features

- **실시간 토큰 추적** — 세션 JSONL에서 실제 토큰 수 파싱 (input + output + cache_creation)
- **롤링 윈도우** — 최근 5시간 내 사용량만 추적, 오래된 토큰은 자동으로 풀림
- **초 단위 카운트다운** — 매초 갱신되는 실시간 타이머
- **플랜 프리셋** — Pro / Max 5x / Max 20x 자동 설정
- **기존 세션 스캔** — 설치 시 기존 사용량 자동 감지
- **색상 경고** — 70% 이상 노란색, 90% 이상 빨간색

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
  "tokenLimit": 300000,
  "windowHours": 5
}
```

| 옵션 | 설명 | Pro | Max 5x | Max 20x |
|------|------|-----|--------|---------|
| `tokenLimit` | 윈도우당 토큰 한도 | 200K | 1M | 4M |
| `windowHours` | 롤링 윈도우 (시간) | 5 | 5 | 5 |

## How It Works

1. Claude Code 응답 완료 시 `Stop` hook이 실행됩니다
2. Hook이 세션 JSONL에서 실제 `usage` 데이터를 파싱합니다
3. 토큰 사용 기록이 타임스탬프와 함께 롤링 로그에 저장됩니다
4. SwiftBar 플러그인이 매초 갱신하며, 5시간이 지난 토큰은 자동으로 풀립니다

## Menu Bar

```
⚡ 128.5K/200.0K · ⏱ 3h45m12s     일반 사용
⚠️ 195.0K/200.0K · ⏱ 0h12m03s     90% 이상 경고
```

드롭다운:
```
████████████░░░░░░░░ 64.2%
Used:         128,500 tokens
Remaining:     71,500 tokens
Limit:        200,000 tokens
⏱  Next +2,300 in 1h 23m 45s     (가장 오래된 토큰이 풀리는 시간)
🔄  Full recharge in 4h 59m 12s   (전체 충전)
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
