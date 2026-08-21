-- AI Agent tables only (Project Sanctuary)
-- Run AFTER: CREATE EXTENSION IF NOT EXISTS vector;
-- Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS efp_knowledge_chunks (
    id TEXT PRIMARY KEY,
    source VARCHAR(20) NOT NULL,
    section VARCHAR(60) NOT NULL,
    name VARCHAR(120) NOT NULL,
    price VARCHAR(20),
    content TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_efp_knowledge_embedding
    ON efp_knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS chat_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_identifier VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS guest_ai_memory (
    id SERIAL PRIMARY KEY,
    guest_identifier VARCHAR(255) NOT NULL,
    memory_type VARCHAR(20) NOT NULL
        CHECK (memory_type IN ('semantic', 'episodic', 'procedural')),
    content TEXT NOT NULL,
    embedding vector(1024),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_guest_ai_memory_guest
    ON guest_ai_memory (guest_identifier);
CREATE INDEX IF NOT EXISTS ix_guest_ai_memory_embedding
    ON guest_ai_memory USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;