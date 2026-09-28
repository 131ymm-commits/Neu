// Schwarzfall — «Германия. Блэкаут». Наши дни: общеевропейский обвал сети и хронология первых недель без света.
// Условие Schwarzfall_Blackout: стадии по дням, сетевой ввод мёртв, своя энергия живёт; окна подачи в конце — если исследована синхронизация.
// Код написан без доступа к игре (см. README «Что не проверено»).
using System.Linq;
using RimWorld;
using UnityEngine;
using Verse;

namespace Schwarzfall
{
    [DefOf]
    public static class SFDefOf
    {
        public static GameConditionDef Schwarzfall_Blackout;
        public static IncidentDef Schwarzfall_NuclearCloud;
        public static ResearchProjectDef SF_Sync;
        public static ThingDef Schwarzfall_Netzanschluss;
        public static ThingDef Schwarzfall_Inselnetz;
        static SFDefOf() { DefOfHelper.EnsureInitializedInCtor(typeof(SFDefOf)); }
    }

    public class CompProperties_Inselnetz : CompProperties { public float radius = 25f; public CompProperties_Inselnetz() { compClass = typeof(CompInselnetz); } }
    public class CompInselnetz : ThingComp
    {
        public CompProperties_Inselnetz Props => (CompProperties_Inselnetz)props;
        public bool Active { get { var p = parent.TryGetComp<CompPowerTrader>(); return parent.Spawned && (p == null || p.PowerOn); } }
        public bool Covers(IntVec3 c) => Active && c.DistanceTo(parent.Position) <= Props.radius;
        public override void PostDrawExtraSelectionOverlays() { GenDraw.DrawRadiusRing(parent.Position, Props.radius, Active ? Color.green : Color.gray); }
        public static bool Island(Map map, IntVec3 c) => map.listerBuildings.AllBuildingsColonistOfDef(SFDefOf.Schwarzfall_Inselnetz).Any(b => b.TryGetComp<CompInselnetz>()?.Covers(c) == true);
    }

    // Сетевой ввод: 2000 Вт от европейской сети. Мёртв при блэкауте; в окна подачи жив, если есть синхронизация и островной контроллер рядом.
    public class CompPowerPlantGrid : CompPowerPlant
    {
        protected override float DesiredPowerOutput
        {
            get
            {
                var map = parent.Map; if (map == null) return 0f;
                var cond = map.gameConditionManager.GetActiveCondition<GameCondition_Blackout>();
                if (cond == null) return -Props.PowerConsumption;   // сеть жива: полная мощность
                if (cond.GridWindowOpen && SFDefOf.SF_Sync.IsFinished && CompInselnetz.Island(map, parent.Position)) return -Props.PowerConsumption;
                return 0f;
            }
        }
        public override string CompInspectStringExtra()
        {
            var cond = parent.Map?.gameConditionManager.GetActiveCondition<GameCondition_Blackout>();
            if (cond == null) return "SF_GridAlive".Translate();
            if (cond.GridWindowOpen) return SFDefOf.SF_Sync.IsFinished ? (CompInselnetz.Island(parent.Map, parent.Position) ? "SF_GridWindowOn".Translate() : "SF_GridNeedIsland".Translate()) : "SF_GridNeedSync".Translate();
            return "SF_GridDead".Translate();
        }
    }

    public class GameCondition_Blackout : GameCondition
    {
        // стадии по дням с начала условия
        public int Day => TicksPassed / GenDate.TicksPerDay;
        public int Stage => Day < 1 ? 1 : Day < 3 ? 2 : Day < 6 ? 3 : Day < 15 ? 4 : Day < 29 ? 5 : 6;   // 6 — восстановление по частям
        private int lastStage = -1, lastRadioDay = -1, raids, cloudFired;
        private static readonly int[] RaidDays = { 7, 11, 14 };

        // окна подачи (стадия 6): по 6 часов в сутки с 6 до 12, каждые сутки шире на час
        public bool GridWindowOpen
        {
            get
            {
                if (Stage < 6) return false;
                int hour = GenLocalDate.HourOfDay(AffectedMaps.FirstOrDefault() ?? Find.CurrentMap);
                int width = Mathf.Min(24, 6 + (Day - 28));
                return hour >= 6 && hour < 6 + width;
            }
        }
        public override bool ElectricityDisabled => false;   // выключаем не всё, а только сетевой ввод (CompPowerPlantGrid)
        public override string Label => base.Label + " — " + ("SF_Stage" + Stage).Translate();
        public override string TooltipString => base.TooltipString + "\n\n" + ("SF_StageDesc" + Stage).Translate(Day);

        public override void ExposeData()
        {
            base.ExposeData();
            Scribe_Values.Look(ref lastStage, "lastStage", -1); Scribe_Values.Look(ref lastRadioDay, "lastRadioDay", -1);
            Scribe_Values.Look(ref raids, "raids", 0); Scribe_Values.Look(ref cloudFired, "cloudFired", 0);
        }

        public override void GameConditionTick()
        {
            int stage = Stage;
            if (stage != lastStage) { if (lastStage != -1) Find.LetterStack.ReceiveLetter("SF_StageLetter".Translate(stage), ("SF_StageDesc" + stage).Translate(Day), stage >= 4 ? LetterDefOf.ThreatSmall : LetterDefOf.NegativeEvent); lastStage = stage; }
            if (Day != lastRadioDay && GenLocalDate.HourOfDay(Find.CurrentMap) == 8) { lastRadioDay = Day; Radio(); }
            if (Find.TickManager.TicksGame % 2500 != 0) return;   // раз в час
            foreach (Map map in AffectedMaps)
            {
                // стадия 4 «холод и мародёры»: батареи вне острова теряют 1 % в час (нет обогрева, самотёк)
                if (stage == 4) foreach (var b in map.listerBuildings.allBuildingsColonist)
                    { var bat = b.TryGetComp<CompPowerBattery>(); if (bat != null && !CompInselnetz.Island(map, b.Position)) bat.DrawPower(Mathf.Min(bat.StoredEnergy, bat.Props.storedEnergyMax * 0.01f)); }
                // рейды мародёров в заданные дни (один раз каждый)
                if (raids < RaidDays.Length && Day >= RaidDays[raids])
                {
                    raids++;
                    var parms = StorytellerUtility.DefaultParmsNow(IncidentCategoryDefOf.ThreatBig, map);
                    parms.points = Mathf.Max(parms.points * 0.6f, 120f); parms.raidStrategy = RaidStrategyDefOf.ImmediateAttack; parms.forced = true;
                    if (IncidentDefOf.RaidEnemy.Worker.CanFireNow(parms)) IncidentDefOf.RaidEnemy.Worker.TryExecute(parms);
                }
                // облако с АЭС на 3–4-й неделе, один раз
                if (cloudFired == 0 && Day >= 20)
                {
                    cloudFired = 1;
                    var parms = StorytellerUtility.DefaultParmsNow(IncidentCategoryDefOf.Misc, map); parms.forced = true;
                    SFDefOf.Schwarzfall_NuclearCloud.Worker.TryExecute(parms);
                }
            }
        }

        private void Radio()
        {
            string key = "SF_Radio" + Mathf.Clamp(Day, 0, 30);
            if (!key.CanTranslate()) key = "SF_RadioDefault";
            Messages.Message(key.Translate(Day), MessageTypeDefOf.NeutralEvent, false);
        }
    }

    // Мысль: без света тяжело; с островной сетью — легче. (Через Harmony не нужно: даём мысль ситуации из XML в следующей версии.)
    [StaticConstructorOnStartup]
    public static class HarmonyInit { static HarmonyInit() { new HarmonyLib.Harmony("neu.schwarzfall").PatchAll(); } }
}
