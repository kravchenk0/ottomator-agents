# Crawl4AI MCP Server

An MCP (Model Context Protocol) server that provides web crawling capabilities for AI agents using Crawl4AI.

## Features

- **Smart URL Detection**: Automatically detects and handles different URL types (regular webpages, sitemaps, text files)
- **Recursive Crawling**: Follows internal links to discover content
- **Parallel Processing**: Efficiently crawls multiple pages simultaneously
- **Content Chunking**: Intelligently splits content by headers and size for better processing
- **Single Page Crawling**: Quick retrieval of content from a specific URL

## Installation

### Using uv (recommended)

uv venv
.venv\Scripts\activate
uv pip install -e .
crawl4ai-setup

### Using pip

python -m venv .venv
.venv\Scripts\activate
pip install -e .

## Usage

Start the MCP server:

python crawl4ai_mcp.py

## Available Tools

### crawl_single_page

Crawls a single web page and returns its content as markdown.

### smart_crawl_url

Intelligently crawls a URL based on its type (sitemap, text file, or regular webpage).

## Environment Variables

- `HOST`: Host to bind the server to (default: 0.0.0.0)
- `PORT`: Port to bind the server to (default: 8051)
- `TRANSPORT`: Transport protocol to use (sse or stdio, default: sse)