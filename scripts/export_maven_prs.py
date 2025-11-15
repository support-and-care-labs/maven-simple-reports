#!/usr/bin/env python3
"""
Export all open pull requests from Apache Maven repositories to CSV or AsciiDoc with build status
"""
import subprocess
import json
import csv
import sys
import argparse
from datetime import datetime
from pathlib import Path
import re

# Path to authoritative YAML file (adjust if relocated)
YAML_PATH = Path('/Users/ascheman/wrk/maven/maven-support-and-care/maven-mcps/.jqassistant-github.yml')

# List of known Apache Maven repositories (ordered to match .jqassistant-github.yml)
MAVEN_REPOS = [
    'maven-site',
    'maven-sources',
    'maven-build-cache-extension',
    'maven',
    'maven-mvnd',
    'maven-integration-testing',
    'maven-resolver',
    'maven-resolver-ant-tasks',
    'maven-wrapper',
    'maven-clean-plugin',
    'maven-compiler-plugin',
    'maven-deploy-plugin',
    'maven-install-plugin',
    'maven-resources-plugin',
    'maven-site-plugin',
    'maven-surefire',
    'maven-verifier-plugin',
    'maven-ear-plugin',
    'maven-ejb-plugin',
    'maven-jar-plugin',
    'maven-rar-plugin',
    'maven-war-plugin',
    'maven-acr-plugin',
    'maven-shade-plugin',
    'maven-source-plugin',
    'maven-jlink-plugin',
    'maven-jmod-plugin',
    'maven-changelog-plugin',
    'maven-changes-plugin',
    'maven-checkstyle-plugin',
    'maven-doap-plugin',
    'maven-javadoc-plugin',
    'maven-jdeps-plugin',
    'maven-jxr',
    'maven-pmd-plugin',
    'maven-project-info-reports-plugin',
    'maven-antrun-plugin',
    'maven-archetype',
    'maven-artifact-plugin',
    'maven-assembly-plugin',
    'maven-dependency-plugin',
    'maven-enforcer',
    'maven-gpg-plugin',
    'maven-help-plugin',
    'maven-invoker-plugin',
    'maven-jarsigner-plugin',
    'maven-jdeprscan-plugin',
    'maven-plugin-tools',
    'maven-release',
    'maven-remote-resources-plugin',
    'maven-scm',
    'maven-scm-publish-plugin',
    'maven-scripting-plugin',
    'maven-stage-plugin',
    'maven-toolchains-plugin',
    'maven-archiver',
    'maven-artifact-transfer',
    'maven-common-artifact-filters',
    'maven-dependency-analyzer',
    'maven-dependency-tree',
    'maven-file-management',
    'maven-filtering',
    'maven-invoker',
    'maven-jarsigner',
    'maven-mapping',
    'maven-project-utils',
    'maven-reporting-api',
    'maven-reporting-exec',
    'maven-reporting-impl',
    'maven-script-interpreter',
    'maven-shared-incremental',
    'maven-shared-io',
    'maven-shared-jar',
    'maven-shared-resources',
    'maven-shared-utils',
    'maven-verifier',
    'maven-doxia',
    'maven-doxia-site',
    'maven-doxia-sitetools',
    'maven-doxia-book-maven-plugin',
    'maven-doxia-book-renderer',
    'maven-doxia-converter',
    'maven-doxia-linkcheck',
    'maven-archetypes',
    'maven-parent',
    'maven-apache-parent',
    'maven-apache-resources',
    'maven-fluido-skin',
    'maven-dist-tool',
    'maven-gh-actions-shared',
    'maven-jenkins-env',
    'maven-jenkins-lib',
    'maven-indexer',
    'maven-plugin-testing',
    'maven-wagon',
    'maven-studies',
    'maven-repository-tools',
    'maven-doxia-ide',
]

def get_prs_for_repo(repo):
    """Get open PRs for a specific repository"""
    cmd = [
        'gh', 'pr', 'list',
        '--repo', f'apache/{repo}',
        '--state', 'open',
        '--json', 'number,title,author,createdAt,updatedAt,url,isDraft,labels,headRefOid,statusCheckRollup',
        '--limit', '1000'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        prs = json.loads(result.stdout)
        # Add repository name to each PR
        for pr in prs:
            pr['repository'] = {'name': repo}
        return prs
    except subprocess.CalledProcessError:
        # Repo might not exist or have no PRs
        return []

def get_build_status(pr):
    """Extract build status from PR's statusCheckRollup"""
    rollup = pr.get('statusCheckRollup')

    if not rollup:
        return 'UNKNOWN', ''

    # Get overall state
    state = 'UNKNOWN'
    build_url = ''

    # Check for combined status
    for context in rollup:
        context_name = context.get('context', '')
        context_state = context.get('state', context.get('conclusion', 'UNKNOWN'))
        context_url = context.get('targetUrl', '')

        # Prioritize CI/Jenkins/GitHub Actions statuses
        if any(ci in context_name.lower() for ci in ['jenkins', 'ci/', 'github-actions', 'build']):
            if context_state in ['SUCCESS', 'SUCCESSFUL', 'COMPLETED']:
                if state != 'FAILURE':  # Don't override failure
                    state = 'SUCCESS'
                    if not build_url:
                        build_url = context_url
            elif context_state in ['FAILURE', 'FAILED', 'ERROR']:
                state = 'FAILURE'
                build_url = context_url
            elif context_state in ['PENDING', 'IN_PROGRESS']:
                if state not in ['FAILURE', 'SUCCESS']:
                    state = 'PENDING'
                    if not build_url:
                        build_url = context_url

        # Fallback to any status
        if state == 'UNKNOWN' and context_state:
            state = context_state
            build_url = context_url

    return state, build_url

def get_all_maven_prs():
    """Get all open PRs from Maven repositories"""
    all_prs = []

    # Remove archived repos from the list and YAML first
    global MAVEN_REPOS
    MAVEN_REPOS = filter_and_cleanup_archived(MAVEN_REPOS)

    for repo in MAVEN_REPOS:
        print(f"Fetching PRs from {repo}...", file=sys.stderr)
        prs = get_prs_for_repo(repo)
        if prs:
            print(f"  Found {len(prs)} open PRs", file=sys.stderr)
            all_prs.extend(prs)

    return all_prs

def export_to_csv(prs, filename='/tmp/maven_open_prs.csv'):
    """Export PRs to CSV file"""
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'Repository',
            'PR Number',
            'Title',
            'Author',
            'Created',
            'Updated',
            'Draft',
            'Build Status',
            'Build URL',
            'Labels',
            'PR URL'
        ])

        # Sort by repository name, then PR number
        prs.sort(key=lambda x: (x['repository']['name'], x['number']))

        # Data rows
        for pr in prs:
            labels = ', '.join([label['name'] for label in pr.get('labels', [])])
            build_status, build_url = get_build_status(pr)

            writer.writerow([
                pr['repository']['name'],
                pr['number'],
                pr['title'],
                pr['author']['login'],
                pr['createdAt'][:10],  # Just the date part
                pr['updatedAt'][:10],
                'Yes' if pr.get('isDraft', False) else 'No',
                build_status,
                build_url,
                labels,
                pr['url']
            ])

    return filename

def export_to_asciidoc(prs, filename='/tmp/maven_open_prs.adoc'):
    """Export PRs to AsciiDoc file"""
    # Group PRs by repository
    repos = {}
    for pr in prs:
        repo_name = pr['repository']['name']
        if repo_name not in repos:
            repos[repo_name] = []
        repos[repo_name].append(pr)

    # Sort repositories by name
    sorted_repos = sorted(repos.items())

    with open(filename, 'w', encoding='utf-8') as f:
        # Write header
        now = datetime.now().strftime('%a %b %d %H:%M:%S %Z %Y')
        f.write('= Open Maven PRs\n\n')
        f.write(f'The following Apache Maven projects have open Pull-Requests as of {now}.\n\n')
        f.write('[cols="8,3,2,1", options="header"]\n')
        f.write('|===\n')
        f.write('| Title | Date | Build Status | Id\n\n')

        # Write PRs grouped by repository
        for repo_name, repo_prs in sorted_repos:
            # Sort PRs by creation date (newest first)
            repo_prs.sort(key=lambda x: x['createdAt'], reverse=True)

            # Repository header row (spans all columns)
            repo_url = f'https://github.com/apache/{repo_name}/pulls'
            f.write(f'4+| *{repo_url}[{repo_name}]*\n')

            # Write each PR
            for pr in repo_prs:
                build_status, build_url = get_build_status(pr)

                # Format build status with link if URL available
                if build_url:
                    status_text = f'{build_url}[{build_status}]'
                else:
                    status_text = build_status

                # Write row: Title | Date | Build Status | Id
                f.write(f'| {pr["title"]}\n')
                f.write(f'| {pr["createdAt"]}\n')
                f.write(f'| {status_text}\n')
                f.write(f'| {pr["url"]}[{pr["number"]}]\n')

            f.write('\n')  # Empty line between repositories

        f.write('|===\n')

    return filename

def gh_check_repo_archived(repo):
    """Return True if github repo apache/<repo> is archived. Uses 'gh' CLI."""
    try:
        result = subprocess.run(
            ['gh', 'repo', 'view', f'apache/{repo}', '--json', 'archived'],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        return bool(data.get('archived', False))
    except FileNotFoundError:
        print("Warning: 'gh' CLI not found; skipping archived checks.", file=sys.stderr)
        return False
    except subprocess.CalledProcessError:
        # Could be permission or repo not found; treat as not archived to avoid accidental deletion
        print(f"Warning: unable to fetch repo metadata for apache/{repo}; skipping archived check.", file=sys.stderr)
        return False
    except json.JSONDecodeError:
        print(f"Warning: unexpected response when checking apache/{repo}; skipping archived check.", file=sys.stderr)
        return False

def remove_repo_from_yaml(repo, yaml_path=YAML_PATH):
    """Remove lines referencing the given repo from the YAML include list."""
    if not yaml_path.exists():
        return False
    pattern = re.compile(rf'^\s*-+\s*github:repository::https://github\.com/apache/{re.escape(repo)}\b.*$', re.IGNORECASE)
    try:
        text = yaml_path.read_text(encoding='utf-8')
        lines = text.splitlines()
        new_lines = [ln for ln in lines if not pattern.match(ln)]
        if len(new_lines) != len(lines):
            yaml_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
            return True
        return False
    except Exception as e:
        print(f"Warning: failed to edit YAML ({e}); skipping removal of {repo} from YAML.", file=sys.stderr)
        return False

def filter_and_cleanup_archived(repos):
    """Check repos for archival status, remove archived from repos list and from YAML file."""
    archived = []
    remaining = []
    for repo in repos:
        if gh_check_repo_archived(repo):
            archived.append(repo)
        else:
            remaining.append(repo)

    if archived:
        print(f"Detected archived repositories: {', '.join(archived)}", file=sys.stderr)
        for r in archived:
            removed = remove_repo_from_yaml(r)
            if removed:
                print(f"  Removed {r} from YAML ({YAML_PATH})", file=sys.stderr)
            else:
                print(f"  Did not remove {r} from YAML (not present or error)", file=sys.stderr)
    return remaining

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Export all open pull requests from Apache Maven repositories'
    )
    parser.add_argument(
        '--format',
        choices=['csv', 'asciidoc'],
        default='csv',
        help='Output format (default: csv)'
    )
    parser.add_argument(
        '--output',
        '-o',
        help='Output file path (default: /tmp/maven_open_prs.{csv|adoc})'
    )
    parser.add_argument(
        '--author',
        help='Filter PRs by author (e.g., "dependabot[bot]")'
    )
    parser.add_argument(
        '--dependabot',
        action='store_true',
        help='Filter to only show DependaBot PRs (shortcut for --author "app/dependabot")'
    )

    args = parser.parse_args()

    # Handle dependabot flag
    if args.dependabot:
        args.author = 'app/dependabot'

    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        ext = 'adoc' if args.format == 'asciidoc' else 'csv'
        output_file = f'/tmp/maven_open_prs.{ext}'

    print("Fetching open PRs from Apache Maven repositories...\n", file=sys.stderr)
    prs = get_all_maven_prs()

    # Filter by author if specified
    if args.author:
        original_count = len(prs)
        prs = [pr for pr in prs if pr['author']['login'] == args.author]
        print(f"Filtered to author '{args.author}': {len(prs)} of {original_count} PRs", file=sys.stderr)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Total Maven PRs found: {len(prs)}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Export in requested format
    if args.format == 'asciidoc':
        filename = export_to_asciidoc(prs, output_file)
        print(f"Exported AsciiDoc to: {filename}\n", file=sys.stderr)
    else:
        filename = export_to_csv(prs, output_file)
        print(f"Exported CSV to: {filename}\n", file=sys.stderr)

    # Print summary by status
    statuses = {}
    for pr in prs:
        status, _ = get_build_status(pr)
        statuses[status] = statuses.get(status, 0) + 1

    print("PRs by build status:", file=sys.stderr)
    for status, count in sorted(statuses.items(), key=lambda x: x[1], reverse=True):
        print(f"  {status}: {count}", file=sys.stderr)

    # Print summary by repo
    repos = {}
    for pr in prs:
        repo = pr['repository']['name']
        repos[repo] = repos.get(repo, 0) + 1

    print("\nPRs by repository:", file=sys.stderr)
    for repo, count in sorted(repos.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {repo}: {count}", file=sys.stderr)