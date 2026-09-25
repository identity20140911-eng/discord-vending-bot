import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, Select

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터 저장소 (메모리 DB)
balances = {}       # {user_id: balance}
products = {}       # {product_id: {"name": str, "price": int, "stock": int}}
admin_roles = {}    # {guild_id: role_id}

# 지정해주신 계좌 정보 적용
OWNER_ACCOUNT = "토스뱅크 1908-1067-5720 (예금주: 강민수)"

# ----------------- 1. 충전 시스템 (모달 & 입금 확인) -----------------
class DepositModal(Modal, title="금액 충전하기"):
    depositor_name = discord.ui.TextInput(label="입금자 성함", placeholder="실제 입금하실 분의 성함을 입력하세요.")
    amount = discord.ui.TextInput(label="충전할 금액", placeholder="숫자만 입력하세요 (예: 10000)")

    async def on_submit(self, interaction: discord.Interaction):
        name = self.depositor_name.value.strip()
        try:
            amt = int(self.amount.value.strip())
            if amt <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("충전 금액은 올바른 숫자로 입력해 주세요.", ephemeral=True)
            return

        user_id = interaction.user.id
        balances[user_id] = balances.get(user_id, 0) + amt

        embed = discord.Embed(title="💳 충전 완료 안내", color=0x00FF00)
        embed.add_field(name="입금 계좌", value=OWNER_ACCOUNT, inline=False)
        embed.add_field(name="입금자명", value=name, inline=True)
        embed.add_field(name="충전 금액", value=f"{amt:,}원", inline=True)
        embed.add_field(name="현재 잔액", value=f"{balances[user_id]:,}원", inline=False)
        embed.set_footer(text="입금 확인이 완료되어 잔액이 정상 충전되었습니다.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ----------------- 2. 구매 시스템 -----------------
class ProductSelect(Select):
    def __init__(self):
        options = []
        if not products:
            options.append(discord.SelectOption(label="등록된 제품 없음", description="현재 판매 중인 제품이 없습니다."))
        else:
            for pid, p in products.items():
                options.append(discord.SelectOption(
                    label=p["name"], 
                    description=f"가격: {p['price']:,}원 | 재고: {p['stock']}개", 
                    value=pid
                ))
        super().__init__(placeholder="구매하실 제품을 선택해 주세요.", options=options)

    async def callback(self, interaction: discord.Interaction):
        if not products or self.values[0] not in products:
            await interaction.response.send_message("현재 선택 가능한 제품이 없습니다.", ephemeral=True)
            return

        pid = self.values[0]
        product = products[pid]
        user_id = interaction.user.id
        user_bal = balances.get(user_id, 0)

        if user_bal < product["price"]:
            await interaction.response.send_message(
                f"잔액이 부족합니다. (현재 잔액: {user_bal:,}원 / 필요 금액: {product['price']:,}원)", 
                ephemeral=True
            )
            return
        
        if product["stock"] <= 0:
            await interaction.response.send_message("해당 제품은 품절되었습니다.", ephemeral=True)
            return

        # 결제 처리
        balances[user_id] -= product["price"]
        product["stock"] -= 1

        await interaction.response.send_message(
            f"✅ [{product['name']}] 구매가 완료되었습니다. (남은 잔액: {balances[user_id]:,}원)", 
            ephemeral=True
        )

class PurchaseView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ProductSelect())

# ----------------- 3 & 4. 제품 설정 및 권한 부여 -----------------
def check_permission(guild_id, user: discord.Member):
    if user.guild_permissions.administrator:
        return True
    role_id = admin_roles.get(guild_id)
    if role_id and any(r.id == role_id for r in user.roles):
        return True
    return False

class ProductManageModal(Modal, title="제품 추가 / 수정"):
    pid = discord.ui.TextInput(label="제품 ID (고유 식별자)", placeholder="예: item1")
    name = discord.ui.TextInput(label="제품 이름", placeholder="예: 유컴 1000개")
    price = discord.ui.TextInput(label="가격", placeholder="숫자만 입력")
    stock = discord.ui.TextInput(label="재고 수량", placeholder="숫자만 입력")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            p_id = self.pid.value.strip()
            p_name = self.name.value.strip()
            p_price = int(self.price.value.strip())
            p_stock = int(self.stock.value.strip())
            if p_price < 0 or p_stock < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("가격과 재고는 0 이상의 숫자로 입력해 주세요.", ephemeral=True)
            return

        products[p_id] = {"name": p_name, "price": p_price, "stock": p_stock}
        await interaction.response.send_message(f"✅ 제품 [{p_name}] 등록 및 수정이 완료되었습니다.", ephemeral=True)

class ProductDeleteModal(Modal, title="제품 삭제"):
    pid = discord.ui.TextInput(label="삭제할 제품 ID", placeholder="예: item1")

    async def on_submit(self, interaction: discord.Interaction):
        p_id = self.pid.value.strip()
        if p_id in products:
            del products[p_id]
            await interaction.response.send_message(f"✅ 제품 ID [{p_id}] 삭제가 완료되었습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("해당 제품 ID를 찾을 수 없습니다.", ephemeral=True)

class ManageView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="➕ 제품 추가/수정", style=discord.ButtonStyle.blurple)
    async def add_edit_btn(self, interaction: discord.Interaction, button: Button):
        if not check_permission(interaction.guild.id, interaction.user):
            await interaction.response.send_message("제품 관리 권한이 없습니다.", ephemeral=True)
            return
        await interaction.response.send_modal(ProductManageModal())

    @discord.ui.button(label="🗑️ 제품 삭제", style=discord.ButtonStyle.red)
    async def delete_btn(self, interaction: discord.Interaction, button: Button):
        if not check_permission(interaction.guild.id, interaction.user):
            await interaction.response.send_message("제품 관리 권한이 없습니다.", ephemeral=True)
            return
        await interaction.response.send_modal(ProductDeleteModal())

# ----------------- 명령어 세팅 -----------------
@bot.command(name="자판기설정")
async def setup_vending(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("관리자만 이용할 수 있는 명령어입니다.")
        return
    
    embed = discord.Embed(
        title="🐱 냥코대전쟁 유컴 자동 자판기", 
        description="아래 버튼을 눌러 충전, 구매, 제품 관리를 진행해 주세요.", 
        color=0xFF6600
    )
    
    view = View(timeout=None)
    view.add_item(Button(label="💳 잔액 충전", style=discord.ButtonStyle.green, custom_id="deposit_btn"))
    view.add_item(Button(label="🛒 제품 구매", style=discord.ButtonStyle.blurple, custom_id="buy_btn"))
    view.add_item(Button(label="⚙️ 제품 관리", style=discord.ButtonStyle.grey, custom_id="manage_btn"))
    
    await ctx.send(embed=embed, view=view)

@bot.command(name="관리역할지정")
async def set_admin_role(ctx, role: discord.Role):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("관리자만 이용할 수 있는 명령어입니다.")
        return
    admin_roles[ctx.guild.id] = role.id
    await ctx.send(f"✅ 제품 설정 권한 역할이 [{role.name}] (으)로 지정되었습니다.")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        if custom_id == "deposit_btn":
            await interaction.response.send_modal(DepositModal())
        elif custom_id == "buy_btn":
            view = PurchaseView()
            await interaction.response.send_message("구매하실 제품을 선택해 주세요:", view=view, ephemeral=True)
        elif custom_id == "manage_btn":
            if not check_permission(interaction.guild.id, interaction.user):
                await interaction.response.send_message("제품 관리 권한이 없습니다.", ephemeral=True)
                return
            view = ManageView()
            await interaction.response.send_message("원하시는 관리 작업을 선택해 주세요:", view=view, ephemeral=True)

@bot.event
async def on_ready():
    print(f"로그인 완료: {bot.user}")

bot.run("MTU1Mjk0ODc4NDY0MjkxNjM4Mg.Gx3v8C.XNrntp8iFPwiytjxfuegcyW7FxT2H20L3O-oiI.")
