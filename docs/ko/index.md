# NamiFAX 매뉴얼

NamiFAX는 HylaFAX 팩스 서버의 웹 프런트엔드입니다. Python(Pyramid, SQLAlchemy)으로 만들었으며, 관리자는 브라우저로 사용자와 권한, 팩스 회선(모뎀), 분류 등을 관리하고 사용자는 어디서든 팩스를 보고 보내고 보관할 수 있습니다.

## 어디서부터 읽을까요

| 하려는 일 | 읽을 곳 |
|---|---|
| NamiFAX가 무엇이고 무엇을 할 수 있는지 알고 싶다 | [개요](guide/overview.md) |
| 처음 설치한다 | [설치 시작](install/index.md) → [HylaFAX 서버 준비](install/hylafax-server.md) → [HylaFAX 연동 설치](install/hylafax.md) |
| 이미 AvantFAX 3.x를 쓰고 있다 | [AvantFAX 3.x에서 옮기기](install/migration.md) |
| 운영에 올리기 전에 점검한다 | [운영 점검 목록](install/operations-checklist.md) |
| 팩스를 받고 보내고 찾는다 | [사용 매뉴얼](manual/index.md) |
| 사용자, 팩스 회선, 저장소를 관리한다 | [관리자 매뉴얼](manual/admin/index.md) |

!!! warning "시험 범위"
    이 저장소에서는 실제 HylaFAX, CUPS, S3에 붙여 시험하지 못했습니다. 운영에 쓰기 전에 시험 서버에서 [HylaFAX 연동 설치](install/hylafax.md)와 [운영 점검 목록](install/operations-checklist.md)을 한 번 거치십시오.
