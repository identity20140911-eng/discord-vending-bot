import asyncio
import threading
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, request

# Flask 웹서버 (입금 알림 수신용)
app = Flask(__name__)

# 임시 데이터베이스 (유저 잔액 및 입금 신청 내역)
user_balances = {}  # {user_id: balance}
pending_deposits = {}  # {deposit_name: (user_id, amount)}

# 봇 설정
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
  print(f"로그인 완료: {bot.user.name}")
  try:
    synced = await bot.tree.sync()
    print(f"슬래시 명령어 {len(synced)}개 동기화 완료!")
  except Exception as e:
    print(f"동기화 에러: {e}")


# --- 웹훅 API: 입금 알림 수신 시 자동 충전 처리 ---
@app.route("/deposit_webhook", methods=["POST"])
def deposit_webhook():
  data = request.json
  depositor_name = data.get("name")
  amount = data.get("amount")

  if depositor_name in pending_deposits:
    user_id, expected_amount = pending_deposits[depositor_name]

    # 유저가 자유롭게 신청한 금액과 실제 입금된 금액이 일치하는지 확인
    if int(amount) == int(expected_amount):
      user_balances[user_id] = user_balances.get(user_id, 0) + int(amount)
      del pending_deposits[depositor_name]
      print(f"[자동충전 성공] 유저 ID {user_id} - {amount}원 충전완료")
      return {"status": "success", "message": "충전 완료"}, 200

  return {"status": "ignored", "message": "일치하는 입금 신청 없음"}, 400


# --- 자유 금액 입력 모달 창 ---
class FreeDepositModal(discord.ui.Modal, title="💳 자유 금액 입금 신청"):
  depositor_name = discord.ui.TextInput(
      label="입금자 성함",
      placeholder="예: 강민수",
      required=True,
      max_length=10,
  )
  amount = discord.ui.TextInput(
      label="충전할 금액 (자유롭게 입력)",
      placeholder="예: 3500 (원 단위 숫자만 입력)",
      required=True,
  )

  async def on_submit(self, interaction: discord.Interaction):
    try:
      # 숫자만 추출
      clean_amount_str = self.amount.value.replace(",", "").replace("원", "").strip()
      amt = int(clean_amount_str)

      if amt <= 0:
        await interaction.response.send_message(
            "1원 이상의 금액을 입력해 주세요.", ephemeral=True
        )
        return

      name = self.depositor_name.value.strip()

      # 입금 대기 목록에 등록 (이름: 유저ID, 자유입력금액)
      pending_deposits[name] = (interaction.user.id, amt)

      embed = discord.Embed(
          title="⏳ 자동 입금 확인 대기 중",
          description=(
              f"**입금 계좌:** 토스뱅크 `1908-1067-5720` (강민수)\n"
              f"**입금자명:** `{name}`\n"
              f"**신청 금액:** `{amt:,}원`\n\n"
              f"위 계좌로 **`{amt:,}원`**을 정확히 입금해 주세요.\n"
              "입금이 확인되면 시스템이 자동으로 잔액을 충전합니다!"
          ),
          color=0xF1C40F,
      )
      await interaction.response.send_message(embed=embed, ephemeral=True)
    except ValueError:
      await interaction.response.send_message(
          "금액은 숫자만 정확히 입력해 주세요! (예: 5000)", ephemeral=True
      )


# --- /자판기설정 슬래시 명령어 ---
@bot.tree.command(
    name="자판기설정", description="냥코대전쟁 유컴 자판기 패널을 생성합니다."
)
async def vending_setup(interaction: discord.Interaction):
  embed = discord.Embed(
      title="🐱 냥코대전쟁 유컴 자동 자판기",
      description=(
          "아래 버튼을 눌러 원하시는 작업을 선택해 주세요.\n\n"
          "💳 **잔액 충전**: 원하는 금액만큼 자유 충전 (자동 확인)\n"
          "🛒 **제품 구매**: 등록된 유컴 및 아이템 구매\n"
          "👤 **내 정보**: 현재 잔액 확인"
      ),
      color=0x3498DB,
  )

  view = discord.ui.View()
  btn_charge = discord.ui.Button(
      label="잔액 충전", style=discord.ButtonStyle.success, emoji="💳"
  )
  btn_info = discord.ui.Button(
      label="내 정보", style=discord.ButtonStyle.secondary, emoji="👤"
  )

  async def charge_callback(interaction: discord.Interaction):
    await interaction.response.send_modal(FreeDepositModal())

  async def info_callback(interaction: discord.Interaction):
    bal = user_balances.get(interaction.user.id, 0)
    await interaction.response.send_message(
        f"💰 **{interaction.user.name}** 님의 현재 잔액:"
        f" **{bal:,}원**입니다.",
        ephemeral=True,
    )

  btn_charge.callback = charge_callback
  btn_info.callback = info_callback

  view.add_item(btn_charge)
  view.add_item(btn_info)

  await interaction.response.send_message(embed=embed, view=view)


# 웹서버와 봇 동시 실행
def run_flask():
  app.run(host="0.0.0.0", port=10000)


threading.Thread(target=run_flask).start()

# 봇 토큰 입력 (네 봇 토큰 유지)
bot.run("MTU1MDg1NjY4MTM2ODMyNjIyMw.GSIgpn.XkXOqhCOfTiXTs_iHpcStdKk3o76l4RupsuDo4")
