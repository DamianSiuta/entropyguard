# 🔒 EntropyGuard - Open Core Strategy & Security Guidelines

## 📋 Executive Summary

This document defines the **Open Core** business model strategy for EntropyGuard, establishing clear legal and technical boundaries between the Open Source (Community) and Commercial (Enterprise) editions. This strategy ensures IP protection, legal compliance, and maintains the integrity of both open-source contributions and commercial offerings.

---

## 🎯 Open Core Model Overview

EntropyGuard follows the **Open Core** business model, where:

- **Core functionality** (CLI tool, data processing pipeline) is **fully open source** and freely available under MIT License
- **Enterprise features** (Control Plane, Dashboard, API, SSO, Compliance tools) are **proprietary** and require a commercial license
- **Clear separation** is maintained through directory structure, `.gitignore` patterns, and licensing

### Community Edition (Open Source)
- ✅ CLI tool (`entropyguard` command)
- ✅ Core data processing pipeline
- ✅ Semantic deduplication engine
- ✅ PII removal & sanitization
- ✅ All data format support (Excel, Parquet, CSV, JSONL)
- ✅ Docker support
- ✅ Basic audit logging
- **License:** MIT License (see LICENSE file)
- **Repository:** Public GitHub repository
- **Contributions:** Welcome from community

### Enterprise Edition (Commercial)
- ✅ Everything in Community Edition
- ✅ Web Dashboard (Real-time analytics platform)
- ✅ RESTful API
- ✅ Real-time Telemetry & Monitoring
- ✅ Alert System (Watchtower)
- ✅ Log Explorer (Advanced search & filtering)
- ✅ Role-Based Access Control (RBAC)
- ✅ JWT Authentication
- ✅ Single Sign-On (SSO) - SAML 2.0, OAuth 2.0
- ✅ Compliance Tools (GDPR, HIPAA, SOC 2)
- ✅ Enhanced Audit Logs (Immutable audit trails)
- **License:** Commercial (contact sales)
- **Repository:** Private (separate from open source)
- **Distribution:** Licensed customers only

---

## 🔐 Anti-Leak Security Checklist

This checklist must be reviewed before **every** commit to ensure Enterprise code is never accidentally committed to the public repository.

### Pre-Commit Verification

- [ ] **No Enterprise directories:** Verify no files from `control-plane/`, `ee/`, `enterprise/`, `proprietary/`, `commercial/` are staged
- [ ] **No license keys:** Verify no `*.license`, `license.key`, `enterprise.key` files are staged
- [ ] **No internal docs:** Verify no `*_ENTERPRISE*.md`, `*_INTERNAL*.md` files are staged
- [ ] **No deployment configs:** Verify no `docker-compose.enterprise.yml`, `k8s/` (enterprise) files are staged
- [ ] **No build artifacts:** Verify no `*.enterprise`, `*.ee`, `dist-enterprise/` files are staged
- [ ] **Git status check:** Run `git status` and verify no Enterprise-related files appear

### Automated Protection

- [x] **`.gitignore` configured:** Enterprise patterns are blocked
- [ ] **Pre-commit hooks:** Git hooks installed to block Enterprise commits (RECOMMENDED)
- [ ] **CI/CD checks:** Automated verification in GitHub Actions (RECOMMENDED)
- [ ] **Code review:** All commits reviewed before merging (MANDATORY)

### Manual Verification Commands

Before committing, run these commands to verify:

```bash
# Check for Enterprise directories
git status | grep -E "(control-plane|ee/|enterprise/|proprietary/|commercial/)"

# Check for license keys
git status | grep -E "(\.license|license\.key|enterprise\.key)"

# Check for internal documentation
git status | grep -E "(ENTERPRISE|INTERNAL|COMMERCIAL)\.md"

# Full check - should return empty if safe
git status --porcelain | grep -v "^??" | grep -E "(control-plane|ee/|enterprise/|license|ENTERPRISE)"
```

If any of these commands return results, **DO NOT COMMIT**. Review and unstage Enterprise files.

---

## 🏗️ Directory Structure & Code Organization

### Recommended Structure (Current Implementation)

```
entropyguard/                    → Public Open Source Repository
├── src/                         (Open Source CLI - MIT License)
│   └── entropyguard/
│       ├── cli/
│       ├── deduplication/
│       ├── ingestion/
│       ├── sanitization/
│       └── validation/
├── tests/                       (Open Source tests)
├── docs/                        (Public documentation)
├── LICENSE                      (MIT License)
├── README.md                    (Public documentation)
├── .gitignore                   (Enterprise protection layer)
│
└── control-plane/               (IGNORED - Enterprise code)
    ├── app/                     (Proprietary API backend)
    ├── dashboard/               (Proprietary React frontend)
    └── docker-compose.yml       (Enterprise deployment)
```

**Important:** The `control-plane/` directory is **blocked by `.gitignore`** and should **never** appear in the public repository.

### Alternative Structure (Separate Repositories)

For maximum security, consider this approach:

```
entropyguard-cli/                → Public GitHub repo (Open Source)
├── src/
├── tests/
├── docs/
├── LICENSE (MIT License)
└── README.md

entropyguard-enterprise/         → Private repository (Commercial)
├── control-plane/
│   ├── app/
│   └── dashboard/
├── enterprise-extensions/
└── LICENSE (Commercial)
```

### Where to Store Code

| Code Type | Location | Repository | License |
|-----------|----------|------------|---------|
| **CLI Tool** | `src/entropyguard/` | Public | MIT License |
| **Core Pipeline** | `src/entropyguard/` | Public | MIT License |
| **Tests (CLI)** | `tests/` | Public | MIT License |
| **Control Plane API** | `control-plane/app/` | Private/Ignored | Commercial |
| **Dashboard** | `control-plane/dashboard/` | Private/Ignored | Commercial |
| **SSO Integration** | `control-plane/app/` | Private/Ignored | Commercial |
| **Compliance Tools** | `control-plane/app/` | Private/Ignored | Commercial |

---

## ⚖️ Legal Separation & Compliance

### Licensing Boundaries

**Community Edition (Open Source):**
- Code in `src/` directory: MIT License
- Freely redistributable
- Modification allowed
- Commercial use allowed (within license terms)

**Enterprise Edition (Commercial):**
- Code in `control-plane/` directory: Proprietary/Commercial License
- **NOT** redistributable without license
- **NOT** modifiable without license
- Requires paid subscription

### Legal Requirements

1. **No Code Mixing:** Enterprise code must NEVER be in the same files as Open Source code
2. **Clear Documentation:** README.md clearly separates Community vs Enterprise features
3. **License Headers:** All Enterprise source files must contain proprietary license headers:
   ```python
   # Copyright (c) 2025 EntropyGuard Enterprise
   # Proprietary Software - All Rights Reserved
   # Commercial License Required
   # NOT part of Open Source release
   ```
4. **Separate Distribution:** Enterprise binaries/documentation distributed separately

---

## 🚨 Risk Mitigation

### High-Risk Scenarios & Solutions

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Accidental commit of Enterprise code** | 🔴 CRITICAL | Pre-commit hooks, CI/CD checks, code reviews |
| **Incomplete .gitignore coverage** | 🟠 HIGH | Regular audits, comprehensive patterns, separate repos |
| **Documentation leak (internal docs)** | 🟠 HIGH | Ignore patterns for `*_INTERNAL*.md`, code reviews |
| **License confusion** | 🟡 MEDIUM | Clear README, license headers, contribution guidelines |
| **Build artifact leak** | 🟡 MEDIUM | Ignore patterns for `*.enterprise`, `dist-enterprise/` |

### Incident Response

If Enterprise code is accidentally committed to the public repository:

1. **IMMEDIATELY** remove the commit (if not yet pushed) or create a revert commit
2. **REVIEW** git history to identify what was exposed
3. **ASSESS** the impact and determine if IP was compromised
4. **CONTACT** legal team if sensitive code was exposed
5. **UPDATE** `.gitignore` and pre-commit hooks to prevent recurrence

---

## 📊 Protection Status

| Protection Layer | Status | Implementation |
|-----------------|--------|----------------|
| `.gitignore` Enterprise patterns | ✅ **ACTIVE** | Comprehensive coverage in place |
| README.md legal notices | ✅ **ACTIVE** | Clear separation documented |
| License separation | ✅ **ACTIVE** | MIT License for Community, Commercial for Enterprise |
| Pre-commit hooks | ⚠️ **RECOMMENDED** | Manual prevention (not yet automated) |
| CI/CD checks | ⚠️ **RECOMMENDED** | Automated verification (not yet implemented) |
| License headers | ⚠️ **RECOMMENDED** | Source file protection (should be added) |
| Separate repositories | ⚠️ **OPTIONAL** | Maximum security (current: monorepo with .gitignore) |

---

## 🎯 Action Items & Roadmap

### Immediate (Required)
- [x] Update `.gitignore` with Enterprise Protection Layer
- [x] Add legal notices to README.md
- [x] Create edition comparison table
- [x] Document Open Core strategy

### Short-term (Recommended)
- [ ] Implement pre-commit hooks (block Enterprise commits)
- [ ] Add CI/CD checks (verify no Enterprise code in PRs)
- [ ] Add license headers to Enterprise source files
- [ ] Create CONTRIBUTING.md with clear guidelines

### Long-term (Optional but Beneficial)
- [ ] Migrate to separate repositories (maximum security)
- [ ] Create Enterprise-specific documentation site
- [ ] Implement automated license verification
- [ ] Set up security scanning for accidental leaks

---

## 📚 Additional Resources

### Documentation
- [Open Source Guide - Legal](https://opensource.guide/legal/)
- [Open Core Model Best Practices](https://opensource.com/article/19/4/open-core-vs-open-source)
- [Git Hooks Documentation](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)

### Tools
- [Pre-commit Framework](https://pre-commit.com/) - Automated pre-commit hooks
- [Git Secrets](https://github.com/awslabs/git-secrets) - Prevents committing secrets
- [GitGuardian](https://www.gitguardian.com/) - Monitors for exposed secrets

---

## 📞 Support & Questions

For questions about:
- **Open Source contributions:** See CONTRIBUTING.md or open an issue
- **Enterprise licensing:** Contact sales@entropyguard.com
- **Security concerns:** security@entropyguard.com
- **Legal questions:** legal@entropyguard.com

---

**Last Updated:** 2025-12-21  
**Maintained by:** EntropyGuard Security & Legal Team  
**Review Frequency:** Quarterly or after any security incident

---

## ✅ Quick Reference Checklist

Before committing to the public repository, verify:

- [ ] No `control-plane/` files staged
- [ ] No `*.license` or `license.key` files staged  
- [ ] No `*_ENTERPRISE*.md` or `*_INTERNAL*.md` files staged
- [ ] No `docker-compose.enterprise.yml` or enterprise k8s configs staged
- [ ] Ran `git status` and reviewed output
- [ ] Code belongs in Open Source edition (CLI, core pipeline)
- [ ] License headers are MIT License (not Commercial)

**When in doubt, ask before committing!**
