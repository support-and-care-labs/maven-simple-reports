#!/usr/bin/env bash
#
# Copyright 2025 The Apache Software Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Create public directory if it doesn't exist
mkdir -p "${REPO_ROOT}/public"

# Run the export script
echo "Generating Dependabot PR report..."
"${SCRIPT_DIR}/export_maven_prs.py" \
    --format asciidoc \
    --dependabot \
    --output "${REPO_ROOT}/public/dependabot-prs.adoc"

# Convert all AsciiDoc files to HTML
echo "Converting AsciiDoc files to HTML..."
for adoc_file in "${REPO_ROOT}/public"/*.adoc; do
    if [ -f "$adoc_file" ]; then
        html_file="${adoc_file%.adoc}.html"
        echo "  Converting $(basename "$adoc_file")..."
        asciidoctor -o "$html_file" "$adoc_file"
    fi
done

echo "Report generated successfully in ${REPO_ROOT}/public/"