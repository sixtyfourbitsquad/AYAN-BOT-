-- Preserve Premium/custom emoji: use copy_message when sending (optional columns)
ALTER TABLE welcome_messages ADD COLUMN IF NOT EXISTS copy_from_chat_id BIGINT;
ALTER TABLE welcome_messages ADD COLUMN IF NOT EXISTS copy_from_message_id INTEGER;

ALTER TABLE premium_messages ADD COLUMN IF NOT EXISTS copy_from_chat_id BIGINT;
ALTER TABLE premium_messages ADD COLUMN IF NOT EXISTS copy_from_message_id INTEGER;
