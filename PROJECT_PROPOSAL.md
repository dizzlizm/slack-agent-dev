# Project Proposal: Systems AI Support Bot

**Date:** December 2024
**Status:** In Development

---

## Problem Statement

The IT help desk handles approximately 5,000 tickets annually. Analysis shows:

- **58% of tickets** are repetitive issues (password resets, VPN questions, connectivity) that could be automated
- **15% of requests** come after hours with no support available
- **23% of tickets** breach our 1-hour first response SLA
- Technicians spend 5-7 minutes per ticket just gathering context from multiple systems

This results in delayed support, inconsistent quality, and technician time wasted on low-complexity tasks.

---

## Proposed Solution

An AI-powered Slack bot ("Systems") that serves as first-line IT support:

1. **Instant Triage** - AI analyzes requests and determines the best action
2. **Automated Resolution** - Handles common issues without human intervention
3. **Smart Escalation** - Creates detailed tickets with full context when needed
4. **Unified Access** - Single interface to Freshservice, Intune, and Meraki

**Current Status:** Core bot is built and functional. Needs AWS migration and feature improvements.

---

## Requirements

### Must Have (Phase 1)
- [ ] AWS infrastructure deployment (Lambda, DynamoDB, API Gateway)
- [ ] Multi-environment setup (dev/prod)
- [ ] Slack signature verification (security)
- [ ] Per-user rate limiting
- [ ] Ticket create/read/update in Freshservice

### Should Have (Phase 2)
- [ ] Knowledge base search integration
- [ ] Conversation memory across sessions
- [ ] Device reboot confirmation workflow
- [ ] Basic analytics dashboard

### Nice to Have (Future)
- [ ] Microsoft Teams support
- [ ] Azure AD password reset
- [ ] Proactive outage notifications

---

## Resources Needed

### Infrastructure (Monthly)
| Resource | Cost |
|----------|------|
| AWS Lambda | ~$50 |
| DynamoDB | ~$25 |
| API Gateway | ~$20 |
| Secrets Manager | ~$5 |
| Gemini API | ~$500 |
| **Total** | **~$600/month** |

### Personnel
| Role | Time Commitment |
|------|-----------------|
| Developer | Primary (existing) |
| DevOps | AWS setup, CI/CD |
| Help Desk Lead | Requirements, testing |

### Access Required
- AWS account with permissions for Lambda, DynamoDB, API Gateway, Secrets Manager
- Slack workspace admin (bot already installed)
- Freshservice API key (existing)
- Gemini API key (existing)
- Intune/Meraki API access (existing)

---

## Timeline

| Phase | Tasks | Duration |
|-------|-------|----------|
| **Phase 1** | AWS migration, security hardening, core features | 2-3 weeks |
| **Phase 2** | KB integration, memory, analytics | 2-3 weeks |
| **Phase 3** | Teams support, advanced features | TBD |

### Immediate Next Steps
1. Deploy infrastructure to AWS (SAM/CloudFormation ready)
2. Configure secrets in AWS Secrets Manager
3. Update Slack app with new endpoint URLs
4. Test in dev environment
5. Deploy to production

---

## Approval

| Role | Name | Date |
|------|------|------|
| Project Sponsor | | |
| IT Director | | |
