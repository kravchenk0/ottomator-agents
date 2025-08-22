# Read secrets from .env file to avoid duplication
# This allows Terraform to use the same .env file as the application

locals {
  # Read .env file content
  env_file_content = fileexists("../.env") ? file("../.env") : ""
  
  # Parse .env file into a map
  env_vars = {
    for line in split("\n", local.env_file_content) :
    split("=", line)[0] => join("=", slice(split("=", line), 1, length(split("=", line))))
    if length(regexall("^[A-Z_]+=.*", trimspace(line))) > 0 && !startswith(trimspace(line), "#")
  }
  
  # Extract specific secrets with fallbacks
  openai_api_key = lookup(local.env_vars, "OPENAI_API_KEY", var.openai_api_key != "" ? var.openai_api_key : "")
  rag_api_keys   = lookup(local.env_vars, "RAG_API_KEYS", var.rag_api_keys != "" ? var.rag_api_keys : "")
  
  # JWT secret generation if not provided
  rag_jwt_secret = var.rag_jwt_secret != "" ? var.rag_jwt_secret : (
    lookup(local.env_vars, "RAG_JWT_SECRET", "") != "" ? 
    lookup(local.env_vars, "RAG_JWT_SECRET", "") : 
    sha256("${local.openai_api_key}-${timestamp()}")
  )
}