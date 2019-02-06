import discord
from discord.ext import commands
import asyncio
from bs4 import BeautifulSoup as soup
from .utils import Pyson


modes = {
    'solo': {
        'name': 'tpp', 'size': 1},
    'duo': {
        'name': 'tpp', 'size': 2},
    'squad': {
        'name': 'tpp', 'size': 4},
    'solo-fpp': {
        'name': 'fpp', 'size': 1},
    'duo-fpp': {
        'name': 'fpp', 'size': 2},
    'squad-fpp': {
        'name': 'fpp', 'size': 4}
}

regions = {	'na': '[NA] North America',
            'as': '[AS] Asia',
            'sea': '[SEA] South East Asia',
            'krjp': '[KRJP] Korea/Japan',
            'oc': '[OC] Oceania',
            'sa': '[SA] South America',
            'eu': '[EU] Europe'
            }


class default:
    mode = 'squad'
    region = 'krjp'


class PUBG():
    def __init__(self, bot):
        self.bot = bot
        self.team = Pyson('./cogs/data/PUBG')
        if 'players' not in self.team.data:
            self.team.data['players'] = {}
        if 'season' not in self.team.data:
            self.team.data['season'] = None
        self.bot.loop.create_task(self.update_season())

    async def no_player(self):
        embed = discord.Embed(
            title='Error', description='등록된 플레이어가 없습니다!', color=0xff0000)
        return embed

    async def error_message(self, playername, message):
        embed = discord.Embed(title='Message from PUBG.OP.GG:', description='Error for player {}:\n{}'.format(
            playername.upper(), message), color=0xff0000)
        embed.to_dict()
        return embed

    async def PUBG_API(self, url):
        try:
            data = await self.bot.aiohttp.get(url)
            data = await data.json()
            return data
        except BaseException as error:
            print('Unhandled exception: ' + str(error))
            raise

    async def parse(self, message):
        mode = None
        region = None
        players = []
        message = message.lower().split()
        data = {}
        for info in message:
            if info in modes:
                mode = info
            if info in regions:
                region = info
            if info not in (list(modes)+list(regions)):
                players.append(info)
        if mode == None:
            mode = default.mode
        if region == None:
            region = default.region
        data['players'] = players
        data['season'] = self.team.data['season']
        data['mode'] = mode
        data['region'] = region
        data['match'] = modes[mode]['name']
        data['size'] = modes[mode]['size']
        return data

    async def getID(self, playername):
        data = await self.bot.aiohttp.get('https://pubg.op.gg/user/{}'.format(playername))
        data = await data.text()
        # get HTML of page
        page = soup(data, "html.parser")
        # get line with player ID
        pID = page.find('div', {'class': 'player-summary__name'})
        if pID is None:
            return {'error': 'player not found'}
        playerid = pID['data-user_id']
        nickname = pID['data-user_nickname']
        # get line with current season
        # season = page.find(
        #     'a', {'class': 'game-server__btn game-server__btn--on'})
        # season = season['data-started-at'][:-18]
        season = page.find(
            'button', {'id': 'selectSeason'})
        season = season['data-status']
        return {'playerid': playerid, 'season': season, 'nickname': nickname}

    @commands.command()
    async def 닉네임등록(self, ctx, player: str=None):
        ''': Link your PUBG name to your discord name'''
        with ctx.typing():
            author = ctx.message.author
            if player is None:
                await ctx.send('{} 닉네임을 올바르게 입력해주세요!'.format(author.mention))
                return
            data = await self.getID(player)
            self.team.data['players'][str(author.id)] = {}
            self.team.data['players'][str(author.id)]['nickname'] = data['nickname']
            self.team.data['players'][str(author.id)]['playerid'] = data['playerid']
            self.team.save
            await ctx.send('{} **{}** 플레이어로 등록되었습니다.'.format(author.mention, data['nickname']))

    @commands.group(invoke_without_command=True)
    async def 전적조회(self, ctx, *, message: str=''):
        ''': Get stats for a PUBG player or your team
        Players who have registered do not need to enter their name to get their stats.'''
        with ctx.typing():
            author = ctx.message.author
            if ctx.invoked_subcommand is None:
                data = await self.parse(message)
                if len(data['players']) == 0:
                    if str(author.id) in self.team.data['players']:
                        data['nickname'] = self.team.data['players'][str(author.id)]['nickname']
                        data['playerid'] = self.team.data['players'][str(author.id)]['playerid']
                        await self.print_stats(ctx, data)
                    else:
                        msg = await self.no_player()
                        await ctx.send(embed=msg)
                else:
                    for player in data['players']:
                        info = await self.getID(player)
                        if 'error' not in data:
                            data['nickname'] = info['nickname']
                            data['playerid'] = info['playerid']
                            await self.print_stats(ctx, data)

                        else:
                            error = await self.error_message(player, 'Playername not found')
                            await ctx.send(embed=error)

    @전적조회.command(name='team', )
    async def team_stats(self, ctx, *, message: str=''):
        data = await self.parse(message)
        for teammate in self.team.data['players'].values():
            data['nickname'] = teammate['nickname']
            data['playerid'] = teammate['playerid']
            await self.print_stats(ctx, data)

    async def get_stats(self, player_data):
        class profile:
            mode = player_data['mode']
            nickname = player_data['nickname']
            playerid = player_data['playerid']
            season = player_data['season']
            server = player_data['region']
            match = player_data['match']
            size = player_data['size']
        url = 'https://pubg.op.gg/api/users/{0.playerid}/ranked-stats?season={0.season}&server={0.server}&queue_size={0.size}&mode={0.match}'.format(profile)
        player_stats = await self.PUBG_API(url)
        print(player_stats)#
        await ctx.send(player_stats)
        return player_stats

    async def print_stats(self, ctx, data):
        player_stats = await self.get_stats(data)
        if 'message' in player_stats:
            if player_stats['message'] != '':
                text = player_stats['message']
            else:
                text = '해당 플레이어는 이번 시즌 기록이 없습니다.'
            error = await self.error_message(data['nickname'], text)
            await ctx.send(embed=error)
        else:
            grade = player_stats.get("grade")
            avg_dmg = round(player_stats.get("stats").get("damage_dealt_avg"), 2)
            region = regions.get(data.get('region'))
            mode = data.get('mode').upper()
            r_points = player_stats.get('stats').get('rank_points')
            r_ranks = player_stats.get('ranks').get('rank_points')
            r_ranks_per = round((r_ranks/player_stats.get('max_ranks').get('rank_points'))*100, 2)
            tier = player_stats.get('tier').get('title')
            
            embed = discord.Embed(title=data['nickname'], url=f'https://pubg.op.gg/user/{data.get("nickname")}?server={data.get("region")}',
                                  description=f'{region}-{mode}\n랭크 포인트: **{r_points}**\n랭크 순위: **{r_ranks}위(상위 {r_ranks_per}%)**\n랭크: **{tier}**', color=0x00ff00)
            embed.add_field(name="승률", value='{}%'.format(round(player_stats['stats']['win_matches_cnt']/player_stats['stats']['matches_cnt']*100, 2), inline=True))   
            embed.add_field(name="누적 치킨", value='{}마리'.format(player_stats['stats']['win_matches_cnt']), inline=True)
            embed.add_field(name="누적 TOP 10(확률%)", value='{0}회({1}%)'.format(player_stats['stats']['topten_matches_cnt'], round((player_stats['stats']['topten_matches_cnt']/player_stats['stats']['matches_cnt'])*100, 2)), inline=True)
            embed.add_field(name="평균 딜량", value=avg_dmg, inline=True)
            embed.add_field(name='누적 킬', value='{}킬'.format(player_stats['stats']['kills_sum']), inline=True)
            if player_stats['stats']['deaths_sum'] is 0:
                embed.add_field(name="K/D", value=player_stats['stats']['kills_sum'], inline=True)
            else:
                embed.add_field(name="K/D", value=round(player_stats['stats']['kills_sum']/player_stats['stats']['deaths_sum'], 2), inline=True)
            embed.set_footer(text='시즌: '+data['season'])
            embed.set_thumbnail(url=player_stats.get('tier').get('image_url'))
            await ctx.send(embed=embed)

    #@commands.command(aliases=['leaderboards'])
    @commands.command()
    async def 혼모노랭킹(self, ctx, *, message: str=''):
        """: See who's the best on your team!"""
        with ctx.typing():
            stats = []
            data = await self.parse(message)
            for teammate in self.team.data['players'].values():
                data['nickname'] = teammate['nickname']
                data['playerid'] = teammate['playerid']
                pstats = await self.get_stats(data)
                pstats['nickname'] = data['nickname']
                if 'message' in pstats:
                    pass
                else:
                    stats.append(pstats)
            stats = sorted(stats, key=lambda x: x['stats']['damage_dealt_avg'], reverse=True)
            place = ''
            players = ''
            damage = ''
            embed = discord.Embed(title=f'{data["mode"].upper()}-{regions[data["region"]]}', description=f'시즌: {data["season"]}', color=0x0000ff)
            if len(stats) > 0:
                for rank, pstats in enumerate(stats):
                    place += '{}\n'.format(rank+1)
                    players += '{}\n'.format(pstats['nickname'])
                    damage += '{}\n'.format(round(pstats['stats']['damage_dealt_avg'], 2))
                embed.add_field(name='순위', value=place)
                embed.add_field(name='플레이어', value=players)
                embed.add_field(name='평균 딜량', value=damage)
            await ctx.send(embed=embed)

    async def update_season(self):
        await self.bot.wait_until_ready()
        while True:
            data = await self.bot.aiohttp.get("https://pubg.op.gg/leaderboard")
            data = await data.text()
            page = soup(data, "html.parser")
            player = page.find('a', {'class': 'leader-board-top3__nickname'})
            player = player.string
            data = await self.getID(player)
            if data['season'] != self.team.data['season']:
                self.team.data['season'] = data['season']
                print(f'새로운 시즌: {self.team.data["season"]}')
                self.team.save
            await asyncio.sleep(3600)

    @commands.command()
    async def 등록해제(self, ctx):
        ': Unlink a PUBG name with your discord'
        if self.team.data['players'].pop(str(ctx.author.id)):
            msg = '등록 해제가 완료되었습니다.'
            self.team.save
        else:
            msg = '아직 등록되지 않았습니다!'
        await ctx.send(f'{ctx.author.mention}, {msg}')


def setup(bot):
    bot.add_cog(PUBG(bot))
