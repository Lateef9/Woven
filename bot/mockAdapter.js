import crypto from 'crypto';

export function generateMockThread() {
  const channelId = crypto.randomUUID();
  const channelName = "engineering-team";
  
  const userAlice = { user_id: crypto.randomUUID(), name: "Alice", platform: "mock" };
  const userBob = { user_id: crypto.randomUUID(), name: "Bob", platform: "mock" };

  const channelInfo = { channel_id: channelId, name: channelName, platform: "mock" };
  const now = Date.now();

  return [
    {
      message_id: crypto.randomUUID(),
      text: "Hey team, the CI pipeline is failing on my PR. Anyone seeing the same issue?",
      timestamp: new Date(now - 300000).toISOString(), // 5 mins ago
      author: userAlice,
      channel: channelInfo
    },
    {
      message_id: crypto.randomUUID(),
      text: "Yeah, looks like the database service isn't spinning up in the test environment.",
      timestamp: new Date(now - 250000).toISOString(),
      author: userBob,
      channel: channelInfo
    },
    {
      message_id: crypto.randomUUID(),
      text: "Ah, I see. I just updated the Dockerfile. I'll push a fix shortly.",
      timestamp: new Date(now - 100000).toISOString(),
      author: userAlice,
      channel: channelInfo
    },
    {
      message_id: crypto.randomUUID(),
      text: "Fix pushed. Here is the PR link: https://github.com/org/repo/pull/123",
      timestamp: new Date(now).toISOString(),
      author: userAlice,
      channel: channelInfo
    }
  ];
}
