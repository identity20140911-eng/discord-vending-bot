const {
  Client,
  GatewayIntentBits,
  REST,
  Routes,
  SlashCommandBuilder
} = require("discord.js");

const TOKEN = process.env.DISCORD_TOKEN;
const CLIENT_ID = process.env.CLIENT_ID;

if (!TOKEN) {
  console.error("❌ DISCORD_TOKEN이 설정되지 않았습니다.");
  process.exit(1);
}

if (!CLIENT_ID) {
  console.error("❌ CLIENT_ID가 설정되지 않았습니다.");
  process.exit(1);
}

const client = new Client({
  intents: [GatewayIntentBits.Guilds]
});

const commands = [
  new SlashCommandBuilder()
    .setName("자판기")
    .setDescription("냥코 자판기를 엽니다.")
].map(command => command.toJSON());

const rest = new REST({ version: "10" }).setToken(TOKEN);

(async () => {
  try {
    console.log("🔄 슬래시 명령어 등록 중...");

    await rest.put(
      Routes.applicationCommands(CLIENT_ID),
      { body: commands }
    );

    console.log("✅ /자판기 등록 완료");
  } catch (error) {
    console.error("❌ 명령어 등록 실패:", error);
  }
})();

client.once("ready", () => {
  console.log(`✅ ${client.user.tag} 온라인!`);
});

client.on("interactionCreate", async interaction => {
  if (!interaction.isChatInputCommand()) return;

  if (interaction.commandName === "자판기") {
    await interaction.reply("🛒 냥코 자판기 준비 중!");
  }
});

client.login(TOKEN);
