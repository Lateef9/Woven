import crypto from 'crypto';

export function generateMockThread() {
  const channelId = crypto.randomUUID();
  const channelName = "weekend-plans";

  const userMaya = { user_id: crypto.randomUUID(), name: "Maya", platform: "mock" };
  const userJordan = { user_id: crypto.randomUUID(), name: "Jordan", platform: "mock" };
  const userSam = { user_id: crypto.randomUUID(), name: "Sam", platform: "mock" };

  const channelInfo = { channel_id: channelId, name: channelName, platform: "mock" };
  const now = Date.now();

  return [
    {
      message_id: crypto.randomUUID(),
      text: "Anyone free this Saturday? I was thinking we finally do that coastal trip to Goa.",
      timestamp: new Date(now - 400000).toISOString(),
      author: userMaya,
      channel: channelInfo
    },
    {
      message_id: crypto.randomUUID(),
      text: "I'm in! Let's stay near Anjuna Beach. I found a place called Sea Breeze Homestay for about 2500 a night.",
      timestamp: new Date(now - 300000).toISOString(),
      author: userJordan,
      channel: channelInfo
    },
    {
      message_id: crypto.randomUUID(),
      text: "Perfect. I can book the IndiGo flight leaving Friday evening from Bangalore.",
      timestamp: new Date(now - 200000).toISOString(),
      author: userSam,
      channel: channelInfo
    },
    {
      message_id: crypto.randomUUID(),
      text: "Also, dinner at Britto's on Saturday night? They do great seafood and live music.",
      timestamp: new Date(now - 100000).toISOString(),
      author: userMaya,
      channel: channelInfo
    },
    {
      message_id: crypto.randomUUID(),
      text: "Done. Jordan handles the homestay, Sam books flights, Maya reserves Britto's. Can't wait!",
      timestamp: new Date(now).toISOString(),
      author: userJordan,
      channel: channelInfo
    }
  ];
}
