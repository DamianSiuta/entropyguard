# Security Policy

## Supported Versions

We actively support the following versions of EntropyGuard with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.6.0+  | :white_check_mark: |
| < 1.6.0 | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of the following methods:

1. **Email:** Send a detailed report to the maintainer (see contact information in repository)
2. **Private Security Advisory:** Use GitHub's private vulnerability reporting feature (if enabled)

### What to Include

When reporting a vulnerability, please include:

- Type of vulnerability (e.g., buffer overflow, injection, etc.)
- Full paths of source file(s) related to the vulnerability
- Location of the affected code (tag/branch/commit or direct link)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability

### Response Timeline

- **Initial Response:** Within 48 hours
- **Status Update:** Within 7 days
- **Fix Timeline:** Depends on severity (see below)

### Severity Levels

- **Critical:** Remote code execution, data breach, authentication bypass
  - **Response:** Immediate (within 24 hours)
  - **Fix:** Within 7 days
  
- **High:** Privilege escalation, sensitive data exposure
  - **Response:** Within 48 hours
  - **Fix:** Within 14 days
  
- **Medium:** Denial of service, information disclosure
  - **Response:** Within 7 days
  - **Fix:** Within 30 days
  
- **Low:** Minor security issues, best practice violations
  - **Response:** Within 14 days
  - **Fix:** Within 90 days

## Security Features

### Local Execution (Air-Gap Compatible)

EntropyGuard is designed for **local execution only**. By default:

- ✅ No network connections are made (except for model downloads on first run)
- ✅ No data is transmitted to external services
- ✅ All processing happens on your local machine
- ✅ Embeddings are generated locally using sentence-transformers

**Note:** The first time you use a model (e.g., `all-MiniLM-L6-v2`), it will be downloaded from Hugging Face. Subsequent runs use the cached model locally.

### Data Privacy

- **Input Data:** Never leaves your machine
- **Embeddings:** Generated and stored locally only
- **Audit Logs:** Written to local files (you control the location)
- **No Telemetry:** EntropyGuard does not collect usage statistics or send data to external services

### Docker Security

- **Non-Root User:** Container runs as user `entropyguard` (UID 1000), not root
- **Minimal Base Image:** Uses `python:3.10-slim` (Debian-based, minimal attack surface)
- **No Unnecessary Packages:** Only essential dependencies are installed
- **Read-Only Volumes:** Consider mounting data volumes as read-only when possible

### Dependency Security

We regularly update dependencies to address security vulnerabilities:

- **Automated Scanning:** Dependabot (if enabled) monitors for known vulnerabilities
- **Manual Reviews:** Critical dependencies are reviewed before updates
- **Pinned Versions:** Production dependencies use version ranges that allow security patches

## Known Security Considerations

### 1. Model Downloads

**Risk:** First-time model downloads connect to Hugging Face.

**Mitigation:**
- Models are cached locally after first download
- Use `HF_HOME` environment variable to control cache location
- For air-gap environments, pre-download models before deployment

### 2. File System Access

**Risk:** EntropyGuard reads and writes files based on user-provided paths.

**Mitigation:**
- Validate input paths (prevent path traversal attacks)
- Use absolute paths or validate relative paths
- Consider running in a sandboxed environment for untrusted data

### 3. Memory Usage

**Risk:** Large datasets may consume significant RAM.

**Mitigation:**
- Use Polars LazyFrame for streaming (when fully implemented)
- Process data in batches for very large files
- Monitor memory usage and set appropriate limits

### 4. Audit Logs

**Risk:** Audit logs may contain metadata about sensitive data.

**Mitigation:**
- Audit logs contain row indices and reasons, not actual data
- Store audit logs in secure locations with appropriate access controls
- Consider encrypting audit logs for compliance requirements

## Security Best Practices

### For Users

1. **Keep Dependencies Updated:**
   ```bash
   pip install --upgrade entropyguard
   ```

2. **Use Non-Root User:**
   - Run EntropyGuard as a non-privileged user
   - In Docker, the container already runs as non-root

3. **Secure File Permissions:**
   - Restrict read access to input files
   - Restrict write access to output directories
   - Use appropriate file permissions (e.g., `chmod 600` for sensitive data)

4. **Validate Input Data:**
   - Verify data sources before processing
   - Use schema validation when possible
   - Sanitize file paths

5. **Monitor Audit Logs:**
   - Review audit logs regularly
   - Store logs securely
   - Rotate logs to prevent disk space issues

### For Developers

1. **Code Review:** All security-related changes require review
2. **Dependency Updates:** Review security advisories for dependencies
3. **Testing:** Include security-focused tests (e.g., input validation, edge cases)
4. **Documentation:** Document security assumptions and limitations

## Compliance

EntropyGuard is designed to support compliance requirements:

- **GDPR:** Local execution ensures data stays within your jurisdiction
- **HIPAA:** No data transmission to external services (with proper configuration)
- **SOC 2:** Audit logging supports compliance tracking
- **Air-Gap:** Suitable for air-gapped environments (with pre-downloaded models)

**Note:** Compliance is ultimately the responsibility of the user. EntropyGuard provides tools (local execution, audit logs) but does not guarantee compliance on its own.

## Security Updates

Security updates are released as patch versions (e.g., 1.6.0 → 1.6.1).

- **Critical vulnerabilities:** Immediate patch release
- **High vulnerabilities:** Patch within 14 days
- **Medium/Low vulnerabilities:** Included in next regular release

Subscribe to GitHub releases or watch the repository to be notified of security updates.

## Contact

For security-related questions or concerns, please contact the maintainer through the repository's contact information.

---

**Last Updated:** 2025-12-20  
**Version:** 1.6.0

