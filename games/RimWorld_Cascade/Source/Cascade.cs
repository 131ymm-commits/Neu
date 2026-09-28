// Каскад — медленная электрическая катастрофа для RimWorld 1.5/1.6.
// Четыре стадии по времени условия: наводки → перегрузка → ионный купол → разряды. Защита: заземляющий контур (радиус),
// экранированный кабель, молниеотвод. Код написан без доступа к игре в среде разработки; см. README «Что не проверено».
using System.Collections.Generic;
using System.Linq;
using RimWorld;
using UnityEngine;
using Verse;

namespace Cascade
{
    public static class CascadeDefOf
    {
        public static GameConditionDef Cascade_Storm;
        public static ThingDef Cascade_GroundingRod;
        public static ThingDef Cascade_LightningRod;
        static CascadeDefOf() { DefOfHelper.EnsureInitializedInCtor(typeof(CascadeDefOf)); }
    }

    // ---------- компоненты построек ----------
    public class CompProperties_Grounding : CompProperties
    {
        public float radius = 12f;
        public CompProperties_Grounding() { compClass = typeof(CompGrounding); }
    }
    public class CompGrounding : ThingComp
    {
        public CompProperties_Grounding Props => (CompProperties_Grounding)props;
        public bool Active
        {
            get
            {
                var power = parent.TryGetComp<CompPowerTrader>();
                return parent.Spawned && (power == null || power.PowerOn);
            }
        }
        public bool Protects(IntVec3 c) => Active && c.DistanceTo(parent.Position) <= Props.radius;
        public override void PostDrawExtraSelectionOverlays()
        {
            GenDraw.DrawRadiusRing(parent.Position, Props.radius, Active ? Color.cyan : Color.gray);
        }
        public override string CompInspectStringExtra()
        {
            return Active ? "Cascade_GroundingActive".Translate(Props.radius.ToString("0")) : "Cascade_GroundingInactive".Translate();
        }
    }

    public class CompProperties_LightningRod : CompProperties
    {
        public float radius = 20f;
        public CompProperties_LightningRod() { compClass = typeof(CompLightningRod); }
    }
    public class CompLightningRod : ThingComp
    {
        public CompProperties_LightningRod Props => (CompProperties_LightningRod)props;
        public bool Covers(IntVec3 c) => parent.Spawned && c.DistanceTo(parent.Position) <= Props.radius;
        public override void PostDrawExtraSelectionOverlays() { GenDraw.DrawRadiusRing(parent.Position, Props.radius, Color.yellow); }
    }

    public class CompProperties_Shielded : CompProperties { public CompProperties_Shielded() { compClass = typeof(CompShielded); } }
    public class CompShielded : ThingComp { }

    public class PlaceWorker_ShowGroundingRadius : PlaceWorker
    {
        public override void DrawGhost(ThingDef def, IntVec3 center, Rot4 rot, Color ghostCol, Thing thing = null)
        {
            var p = def.GetCompProperties<CompProperties_Grounding>(); if (p != null) GenDraw.DrawRadiusRing(center, p.radius, Color.cyan);
        }
    }
    public class PlaceWorker_ShowLightningRadius : PlaceWorker
    {
        public override void DrawGhost(ThingDef def, IntVec3 center, Rot4 rot, Color ghostCol, Thing thing = null)
        {
            var p = def.GetCompProperties<CompProperties_LightningRod>(); if (p != null) GenDraw.DrawRadiusRing(center, p.radius, Color.yellow);
        }
    }

    // ---------- условие ----------
    public class GameCondition_Cascade : GameCondition
    {
        // границы стадий в долях длительности; стадия 4 — последние 25 %
        private static readonly float[] StageEnds = { 0.30f, 0.55f, 0.75f, 1.0f };
        private int lastStage = -1;
        private int domeCycle;   // такт ионного купола: 3 ч выключено, 1 ч включено (незаземлённые сети)

        public int Stage
        {
            get
            {
                float f = Duration <= 0 ? 0f : (float)TicksPassed / Duration;
                for (int i = 0; i < StageEnds.Length; i++) if (f < StageEnds[i]) return i + 1;
                return 4;
            }
        }

        public override string Label => base.Label + " (" + "Cascade_Stage".Translate(Stage) + ")";
        public override string TooltipString => base.TooltipString + "\n\n" + ("Cascade_StageDesc" + Stage).Translate();

        public override void ExposeData()
        {
            base.ExposeData();
            Scribe_Values.Look(ref lastStage, "lastStage", -1);
            Scribe_Values.Look(ref domeCycle, "domeCycle", 0);
        }

        // Ионный купол (стадия 3+): электричество на карте выключается волнами. Заземлённые и экранированные сети обрабатываются
        // отдельно в Harmony-патче PowerNet (см. Patch_PowerNet), здесь — только общий сигнал для игры.
        public override bool ElectricityDisabled => Stage >= 3 && DomeActive;
        public bool DomeActive => (domeCycle % 4) != 3;   // 3 такта из 4 — купол активен

        public override void GameConditionTick()
        {
            int stage = Stage;
            if (stage != lastStage)
            {
                if (lastStage != -1) AnnounceStage(stage);
                lastStage = stage;
            }
            if (Find.TickManager.TicksGame % GenDate.TicksPerHour == 0) domeCycle++;
            foreach (Map map in AffectedMaps)
            {
                if (stage >= 1 && Rand.MTBEventOccurs(StageMtbHours(stage, 6f), GenDate.TicksPerHour, 1f)) Spark(map, stage);
                if (stage >= 2 && Find.TickManager.TicksGame % 250 == 0) DrainBatteries(map, stage);
                if (stage >= 2 && Rand.MTBEventOccurs(StageMtbHours(stage, 10f), GenDate.TicksPerHour, 1f)) ExplodeConduit(map);
                if (stage >= 4 && Rand.MTBEventOccurs(2.5f, GenDate.TicksPerHour, 1f)) Strike(map);
            }
        }

        private static float StageMtbHours(int stage, float baseHours) => Mathf.Max(0.5f, baseHours / stage);

        private void AnnounceStage(int stage)
        {
            Find.LetterStack.ReceiveLetter("Cascade_StageLetterLabel".Translate(stage), ("Cascade_StageDesc" + stage).Translate(),
                stage >= 3 ? LetterDefOf.ThreatBig : LetterDefOf.NegativeEvent);
        }

        // --- защита ---
        public static bool Grounded(Map map, IntVec3 c)
        {
            var rods = map.listerBuildings.AllBuildingsColonistOfDef(CascadeDefOf.Cascade_GroundingRod);
            foreach (var b in rods) { var g = b.TryGetComp<CompGrounding>(); if (g != null && g.Protects(c)) return true; }
            return false;
        }
        public static Building NearestLightningRod(Map map, IntVec3 c)
        {
            Building best = null; float bd = float.MaxValue;
            foreach (var b in map.listerBuildings.AllBuildingsColonistOfDef(CascadeDefOf.Cascade_LightningRod))
            {
                var r = b.TryGetComp<CompLightningRod>(); if (r == null || !r.Covers(c)) continue;
                float d = c.DistanceTo(b.Position); if (d < bd) { bd = d; best = b; }
            }
            return best;
        }
        private static bool Vulnerable(Thing t, Map map)
        {
            if (t.TryGetComp<CompShielded>() != null) return false;
            return !Grounded(map, t.Position);
        }
        private static List<Building> PoweredBuildings(Map map) =>
            map.listerBuildings.allBuildingsColonist.Where(b => b.TryGetComp<CompPower>() != null && b.def != CascadeDefOf.Cascade_GroundingRod).ToList();

        // --- эффекты ---
        private void Spark(Map map, int stage)
        {
            var cands = PoweredBuildings(map).Where(b => Vulnerable(b, map)).ToList();
            if (cands.Count == 0) return;
            var b = cands.RandomElement();
            FleckMaker.ThrowMicroSparks(b.DrawPos, map);
            FleckMaker.ThrowLightningGlow(b.DrawPos, map, 1.2f);
            if (stage >= 2 && Rand.Chance(0.35f)) FireUtility.TryStartFireIn(b.Position, map, 0.15f, null);
            if (Rand.Chance(0.5f)) Messages.Message("Cascade_SparkMsg".Translate(b.LabelShort), b, MessageTypeDefOf.NegativeEvent, false);
        }

        private void DrainBatteries(Map map, int stage)
        {
            float pct = 0.002f * stage;   // раз в 250 тиков: стадия 2 — 0,4 %, стадия 4 — 0,8 % заряда
            foreach (var b in map.listerBuildings.allBuildingsColonist)
            {
                var bat = b.TryGetComp<CompPowerBattery>(); if (bat == null || !Vulnerable(b, map)) continue;
                bat.DrawPower(Mathf.Min(bat.StoredEnergy, bat.Props.storedEnergyMax * pct));
            }
        }

        private void ExplodeConduit(Map map)
        {
            var conduits = map.listerBuildings.allBuildingsColonist.Where(b => b.TryGetComp<CompPowerTransmitter>() != null && b.TryGetComp<CompPower>() is CompPowerTransmitter && Vulnerable(b, map)).ToList();
            if (conduits.Count == 0) return;
            var c = conduits.RandomElement();
            GenExplosion.DoExplosion(c.Position, map, 1.4f, DamageDefOf.Flame, null);
            Messages.Message("Cascade_ConduitMsg".Translate(), c, MessageTypeDefOf.NegativeEvent, false);
        }

        private void Strike(Map map)
        {
            // цель — самая мощная электрическая постройка (по |мощности|), молниеотвод в радиусе перехватывает удар
            var targets = PoweredBuildings(map).Select(b => (b, p: Mathf.Abs(b.TryGetComp<CompPowerTrader>()?.Props.PowerConsumption ?? 0f))).OrderByDescending(x => x.p).Take(5).ToList();
            IntVec3 cell = targets.Count > 0 ? targets.RandomElement().b.Position : CellFinder.RandomCell(map);
            var rod = NearestLightningRod(map, cell);
            if (rod != null)
            {
                cell = rod.Position;
                rod.TakeDamage(new DamageInfo(DamageDefOf.Blunt, 25f));
                map.weatherManager.eventHandler.AddEvent(new WeatherEvent_LightningStrike(map, cell));
                Messages.Message("Cascade_RodMsg".Translate(), rod, MessageTypeDefOf.NeutralEvent, false);
                return;
            }
            if (Grounded(map, cell) && Rand.Chance(0.7f)) cell = CellFinder.RandomCell(map);   // заземление отводит 70 % ударов в поле
            map.weatherManager.eventHandler.AddEvent(new WeatherEvent_LightningStrike(map, cell));
        }
    }

    public class IncidentWorker_Cascade : IncidentWorker_MakeGameCondition
    {
        protected override bool CanFireNowSub(IncidentParms parms)
        {
            if (!base.CanFireNowSub(parms)) return false;
            var map = (Map)parms.target;
            // каскад имеет смысл только у колонии с электричеством
            return map.listerBuildings.allBuildingsColonist.Any(b => b.TryGetComp<CompPower>() != null);
        }
    }

    // ---------- Harmony: заземлённые и экранированные сети живут под куполом ----------
    // PowerNet.PowerNetTick: если электричество «выключено» условием, ваниль обнуляет мощность всех сетей.
    // Мы оставляем ток сетям, у которых есть заземляющий контур (активный) и все передатчики экранированы.
    [StaticConstructorOnStartup]
    public static class HarmonyInit
    {
        static HarmonyInit() { new HarmonyLib.Harmony("neu.cascade").PatchAll(); }
    }

    [HarmonyLib.HarmonyPatch(typeof(GameConditionManager), nameof(GameConditionManager.ElectricityDisabled), HarmonyLib.MethodType.Getter)]
    public static class Patch_ElectricityDisabled
    {
        // Ваниль спрашивает «выключено ли электричество на карте» один раз для всех сетей. Мы отвечаем «нет», если хотя бы
        // одна сеть защищена, и дальше выключаем незащищённые сети сами (Patch_PowerNetTick).
        public static void Postfix(GameConditionManager __instance, ref bool __result)
        {
            if (!__result || __instance.ownerMap == null) return;
            var cond = __instance.GetActiveCondition<GameCondition_Cascade>();
            if (cond == null) return;
            if (__instance.ownerMap.powerNetManager.AllNetsListForReading.Any(n => NetProtected(n))) __result = false;
        }
        public static bool NetProtected(PowerNet net)
        {
            var map = net.Map; if (map == null) return false;
            bool grounded = net.transmitters.Any(t => GameCondition_Cascade.Grounded(map, t.parent.Position));
            if (!grounded) return false;
            return net.transmitters.All(t => t.parent.TryGetComp<CompShielded>() != null || t.parent.def == CascadeDefOf.Cascade_GroundingRod);
        }
    }

    [HarmonyLib.HarmonyPatch(typeof(PowerNet), nameof(PowerNet.PowerNetTick))]
    public static class Patch_PowerNetTick
    {
        // Незащищённая сеть под активным куполом: гасим потребителей, как делает ваниль при солнечной вспышке.
        public static void Postfix(PowerNet __instance)
        {
            var map = __instance.Map; if (map == null) return;
            var cond = map.gameConditionManager.GetActiveCondition<GameCondition_Cascade>();
            if (cond == null || cond.Stage < 3 || !cond.DomeActive) return;
            if (Patch_ElectricityDisabled.NetProtected(__instance)) return;
            foreach (var c in __instance.powerComps) { if (c.PowerOn) c.PowerOn = false; }
        }
    }
}
