# Claude Code Token Monitor

macOS 메뉴바에서 Claude Code 토큰 사용량과 리셋 카운트다운을 실시간으로 확인할 수 있는 SwiftBar 플러그인입니다.

```
⚡ 12.5K/45K · ⏱ 2h34m
```

## Features

- **실시간 토큰 사용량** — 사용 토큰 / 전체 한도 표시
- **리셋 카운트다운** — 다음 토큰 충전까지 남은 시간
- **프로그레스 바** — 드롭다운에서 시각적 사용률 확인
- **자동 추적** — Claude Code Hook으로 사용량 자동 기록
- **자동 리셋** — 윈도우 만료 시 자동으로 카운터 초기화
- **색상 경고** — 70% 이상 노란색, 90% 이상 빨간색

## Requirements

- macOS
- Python 3
- [SwiftBar](https://github.com/swiftbar/SwiftBar)
- Claude Code

## Install

```bash
git clone https://github.com/YOUR_USERNAME/claude-token-monitor.git
cd claude-token-monitor
chmod +x install.sh
./install.sh
```

설치 스크립트가 자동으로:
1. SwiftBar 설치 (없는 경우)
2. 플러그인 파일 복사
3. Claude Code Hook 등록
4. 설정 파일 생성

## Configuration

`~/.claude/dashboard/config.json` 을 수정하세요:

```json
{
  "tokenLimit": 45000,
  "resetIntervalHours": 5,
  "plan": "pro"
}
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `tokenLimit` | 윈도우당 토큰 한도 | 45000 |
| `resetIntervalHours` | 리셋 주기 (시간) | 5 |
| `plan` | 플랜 이름 (표시용) | pro |

## How It Works

1. Claude Code에서 응답이 완료될 때마다 `Stop` hook이 실행됩니다
2. Hook이 세션 파일 크기 변화를 측정하여 토큰 사용량을 추정합니다
3. SwiftBar 플러그인이 30초마다 사용량 데이터를 읽어 메뉴바에 표시합니다
4. 설정된 리셋 주기가 지나면 카운터가 자동으로 초기화됩니다

## Menu Bar

| 표시 | 의미 |
|------|------|
| `⚡ 12.5K/45K` | 사용 토큰 / 전체 한도 |
| `⏱ 2h34m` | 리셋까지 남은 시간 |
| `⚠️` | 90% 이상 사용 경고 |

드롭다운 메뉴에서 상세 정보 확인, 카운터 리셋, 설정 편집이 가능합니다.

## Uninstall

```bash
cd claude-token-monitor
chmod +x uninstall.sh
./uninstall.sh
```

## License

MIT
