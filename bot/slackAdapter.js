import bolt from '@slack/bolt';
import { ingestMessage } from './ingest.js';

const { App } = bolt;

function slackTsToIso(ts) {
  const seconds = Number.parseFloat(String(ts));
  if (Number.isNaN(seconds)) {
    return new Date().toISOString();
  }
  return new Date(seconds * 1000).toISOString();
}

async function resolveUserName(client, userId) {
  if (!userId) return 'unknown';
  try {
    const result = await client.users.info({ user: userId });
    return (
      result.user?.profile?.display_name ||
      result.user?.real_name ||
      result.user?.name ||
      userId
    );
  } catch (error) {
    console.warn(`Could not resolve Slack user ${userId}:`, error.message);
    return userId;
  }
}

async function resolveChannelName(client, channelId) {
  if (!channelId) return 'unknown';
  try {
    const result = await client.conversations.info({ channel: channelId });
    return result.channel?.name || channelId;
  } catch (error) {
    console.warn(`Could not resolve Slack channel ${channelId}:`, error.message);
    return channelId;
  }
}

/**
 * Map a Slack message event into the Phase 1 Message schema.
 */
export async function mapSlackMessageToSchema(message, client) {
  const userId = message.user || 'unknown';
  const channelId = message.channel || 'unknown';
  const [authorName, channelName] = await Promise.all([
    resolveUserName(client, userId),
    resolveChannelName(client, channelId),
  ]);

  return {
    message_id: message.client_msg_id || `${channelId}:${message.ts}`,
    text: message.text || '',
    timestamp: slackTsToIso(message.ts),
    author: {
      user_id: userId,
      name: authorName,
      platform: 'slack',
    },
    channel: {
      channel_id: channelId,
      name: channelName,
      platform: 'slack',
    },
  };
}

function isIngestibleSlackMessage(message) {
  // Only public channel messages (Bolt sets channel_type on Events API payloads)
  if (message.channel_type && message.channel_type !== 'channel') {
    return false;
  }
  // Ignore bot / system noise
  if (message.bot_id || message.subtype) {
    return false;
  }
  if (!message.text || !String(message.text).trim()) {
    return false;
  }
  return true;
}

/**
 * Start Slack Bolt in Socket Mode. Returns the Bolt app instance.
 */
export async function startSlackBot() {
  const token = process.env.SLACK_BOT_TOKEN;
  const signingSecret = process.env.SLACK_SIGNING_SECRET;
  const appToken = process.env.SLACK_APP_TOKEN;

  if (!token || !signingSecret || !appToken) {
    throw new Error(
      'Slack mode requires SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, and SLACK_APP_TOKEN',
    );
  }

  const slackApp = new App({
    token,
    signingSecret,
    socketMode: true,
    appToken,
  });

  slackApp.message(async ({ message, client }) => {
    try {
      if (!isIngestibleSlackMessage(message)) {
        return;
      }

      const mapped = await mapSlackMessageToSchema(message, client);
      await ingestMessage(mapped);
      console.log(
        `Ingested Slack message from ${mapped.author.name} in #${mapped.channel.name}`,
      );
    } catch (error) {
      console.error('Failed to ingest Slack message:', error.message);
    }
  });

  await slackApp.start();
  console.log('Slack Socket Mode listener is running');
  return slackApp;
}

export function hasSlackCredentials() {
  return Boolean(
    process.env.SLACK_BOT_TOKEN &&
      process.env.SLACK_SIGNING_SECRET &&
      process.env.SLACK_APP_TOKEN,
  );
}
