# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do not** open a public issue for security vulnerabilities
2. Email the maintainers directly with details of the vulnerability
3. Include the following in your report:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- Acknowledgment of your report within 48 hours
- Regular updates on the progress of addressing the issue
- Credit in the security advisory (unless you prefer to remain anonymous)

### Scope

The following are in scope for security reports:

- Code execution vulnerabilities
- Authentication/authorization bypasses
- Data exposure issues
- Injection vulnerabilities (SQL, command, etc.)
- Dependency vulnerabilities

### Out of Scope

- Issues in dependencies (please report to the respective project)
- Denial of service attacks
- Social engineering
- Physical security issues

## Security Best Practices

When using Lattice:

1. **API Keys**: Never commit API keys to version control. Use environment variables or `.env` files (which are gitignored).

2. **Database Access**: The default Docker Compose configuration binds to localhost. For production, configure proper authentication and network security.

3. **File Access**: Be cautious when indexing repositories. The tool reads source files and could potentially access sensitive data if pointed at directories containing secrets.

## Security Updates

Security updates will be released as patch versions. Subscribe to releases to stay informed about security fixes.
