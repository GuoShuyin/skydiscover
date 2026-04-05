using PChecker;
using PChecker.Runtime;
using PChecker.Runtime.StateMachines;
using PChecker.Runtime.Events;
using PChecker.Runtime.Exceptions;
using PChecker.Runtime.Logging;
using PChecker.Runtime.Values;
using PChecker.Runtime.Specifications;
using Monitor = PChecker.Runtime.Specifications.Monitor;
using System;
using PChecker.SystematicTesting;
using System.Runtime;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

#pragma warning disable 162, 219, 414, 1998
namespace PImplementation
{
}
namespace PImplementation
{
    public static class GlobalConfig
    {
    }
}
namespace PImplementation
{
    internal partial class eRead : Event
    {
        public eRead() : base() {}
        public eRead (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eRead();}
    }
}
namespace PImplementation
{
    internal partial class eReadResp : Event
    {
        public eReadResp() : base() {}
        public eReadResp (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eReadResp();}
    }
}
namespace PImplementation
{
    internal partial class eWrite : Event
    {
        public eWrite() : base() {}
        public eWrite (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eWrite();}
    }
}
namespace PImplementation
{
    internal partial class eWriteResp : Event
    {
        public eWriteResp() : base() {}
        public eWriteResp (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eWriteResp();}
    }
}
namespace PImplementation
{
    internal partial class eDbRead : Event
    {
        public eDbRead() : base() {}
        public eDbRead (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eDbRead();}
    }
}
namespace PImplementation
{
    internal partial class eDbReadResp : Event
    {
        public eDbReadResp() : base() {}
        public eDbReadResp (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eDbReadResp();}
    }
}
namespace PImplementation
{
    internal partial class eDbRefresh : Event
    {
        public eDbRefresh() : base() {}
        public eDbRefresh (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eDbRefresh();}
    }
}
namespace PImplementation
{
    internal partial class eDbRefreshResp : Event
    {
        public eDbRefreshResp() : base() {}
        public eDbRefreshResp (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eDbRefreshResp();}
    }
}
namespace PImplementation
{
    internal partial class eMonitorDbWrite : Event
    {
        public eMonitorDbWrite() : base() {}
        public eMonitorDbWrite (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eMonitorDbWrite();}
    }
}
namespace PImplementation
{
    internal partial class eMonitorCacheHit : Event
    {
        public eMonitorCacheHit() : base() {}
        public eMonitorCacheHit (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eMonitorCacheHit();}
    }
}
namespace PImplementation
{
    internal partial class SimpleTiDB : StateMachine
    {
        private PMap dbStore = new PMap();
        public class ConstructorEvent : Event{public ConstructorEvent(IPValue val) : base(val) { }}
        
        protected override Event GetConstructorEvent(IPValue value) { return new ConstructorEvent((IPValue)value); }
        public SimpleTiDB() {
            this.sends.Add(nameof(eDbRead));
            this.sends.Add(nameof(eDbReadResp));
            this.sends.Add(nameof(eDbRefresh));
            this.sends.Add(nameof(eDbRefreshResp));
            this.sends.Add(nameof(eMonitorCacheHit));
            this.sends.Add(nameof(eMonitorDbWrite));
            this.sends.Add(nameof(eRead));
            this.sends.Add(nameof(eReadResp));
            this.sends.Add(nameof(eWrite));
            this.sends.Add(nameof(eWriteResp));
            this.sends.Add(nameof(PHalt));
            this.receives.Add(nameof(eDbRead));
            this.receives.Add(nameof(eDbReadResp));
            this.receives.Add(nameof(eDbRefresh));
            this.receives.Add(nameof(eDbRefreshResp));
            this.receives.Add(nameof(eMonitorCacheHit));
            this.receives.Add(nameof(eMonitorDbWrite));
            this.receives.Add(nameof(eRead));
            this.receives.Add(nameof(eReadResp));
            this.receives.Add(nameof(eWrite));
            this.receives.Add(nameof(eWriteResp));
            this.receives.Add(nameof(PHalt));
        }
        
        public void Anon(Event currentMachine_dequeuedEvent)
        {
            SimpleTiDB currentMachine = this;
            PNamedTuple req = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt TMP_tmp0 = ((PInt)0);
            PInt TMP_tmp1 = ((PInt)0);
            PInt TMP_tmp2 = ((PInt)0);
            PInt TMP_tmp3 = ((PInt)0);
            PInt TMP_tmp4 = ((PInt)0);
            PNamedTuple TMP_tmp5 = (new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)));
            PMachineValue TMP_tmp6 = null;
            PMachineValue TMP_tmp7 = null;
            Event TMP_tmp8 = null;
            PInt TMP_tmp9 = ((PInt)0);
            PBool TMP_tmp10 = ((PBool)false);
            PNamedTuple TMP_tmp11 = (new PNamedTuple(new string[]{"key","success"},((PInt)0), ((PBool)false)));
            TMP_tmp0 = (PInt)(((PNamedTuple)req)["key"]);
            TMP_tmp1 = (PInt)(((PNamedTuple)req)["value"]);
            TMP_tmp2 = (PInt)(((PInt)((IPValue)TMP_tmp1)?.Clone()));
            ((PMap)dbStore)[TMP_tmp0] = TMP_tmp2;
            TMP_tmp3 = (PInt)(((PNamedTuple)req)["key"]);
            TMP_tmp4 = (PInt)(((PNamedTuple)req)["value"]);
            TMP_tmp5 = (PNamedTuple)((new PNamedTuple(new string[]{"key","value"}, TMP_tmp3, TMP_tmp4)));
            currentMachine.Announce((Event)new eMonitorDbWrite((new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)))), TMP_tmp5);
            TMP_tmp6 = (PMachineValue)(((PNamedTuple)req)["client"]);
            TMP_tmp7 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp6)?.Clone()));
            TMP_tmp8 = (Event)(new eWriteResp((new PNamedTuple(new string[]{"key","success"},((PInt)0), ((PBool)false)))));
            TMP_tmp9 = (PInt)(((PNamedTuple)req)["key"]);
            TMP_tmp10 = (PBool)(((PBool)true));
            TMP_tmp11 = (PNamedTuple)((new PNamedTuple(new string[]{"key","success"}, TMP_tmp9, TMP_tmp10)));
            TMP_tmp8.Payload = TMP_tmp11;
            currentMachine.SendEvent(TMP_tmp7, (Event)TMP_tmp8);
        }
        public void Anon_1(Event currentMachine_dequeuedEvent)
        {
            SimpleTiDB currentMachine = this;
            PNamedTuple req_1 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt val = ((PInt)0);
            PInt TMP_tmp0_1 = ((PInt)0);
            PBool TMP_tmp1_1 = ((PBool)false);
            PInt TMP_tmp2_1 = ((PInt)0);
            PInt TMP_tmp3_1 = ((PInt)0);
            PInt TMP_tmp4_1 = ((PInt)0);
            PMachineValue TMP_tmp5_1 = null;
            PMachineValue TMP_tmp6_1 = null;
            Event TMP_tmp7_1 = null;
            PInt TMP_tmp8_1 = ((PInt)0);
            PInt TMP_tmp9_1 = ((PInt)0);
            PNamedTuple TMP_tmp10_1 = (new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)));
            val = (PInt)(((PInt)(0)));
            TMP_tmp0_1 = (PInt)(((PNamedTuple)req_1)["key"]);
            TMP_tmp1_1 = (PBool)(((PBool)(((PMap)dbStore).ContainsKey(TMP_tmp0_1))));
            if (TMP_tmp1_1)
            {
                TMP_tmp2_1 = (PInt)(((PNamedTuple)req_1)["key"]);
                TMP_tmp3_1 = (PInt)(((PMap)dbStore)[TMP_tmp2_1]);
                TMP_tmp4_1 = (PInt)(((PInt)((IPValue)TMP_tmp3_1)?.Clone()));
                val = TMP_tmp4_1;
            }
            TMP_tmp5_1 = (PMachineValue)(((PNamedTuple)req_1)["lc"]);
            TMP_tmp6_1 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp5_1)?.Clone()));
            TMP_tmp7_1 = (Event)(new eDbReadResp((new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)))));
            TMP_tmp8_1 = (PInt)(((PNamedTuple)req_1)["key"]);
            TMP_tmp9_1 = (PInt)(((PInt)((IPValue)val)?.Clone()));
            TMP_tmp10_1 = (PNamedTuple)((new PNamedTuple(new string[]{"key","value"}, TMP_tmp8_1, TMP_tmp9_1)));
            TMP_tmp7_1.Payload = TMP_tmp10_1;
            currentMachine.SendEvent(TMP_tmp6_1, (Event)TMP_tmp7_1);
        }
        public void Anon_2(Event currentMachine_dequeuedEvent)
        {
            SimpleTiDB currentMachine = this;
            PNamedTuple req_2 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt val_1 = ((PInt)0);
            PInt TMP_tmp0_2 = ((PInt)0);
            PBool TMP_tmp1_2 = ((PBool)false);
            PInt TMP_tmp2_2 = ((PInt)0);
            PInt TMP_tmp3_2 = ((PInt)0);
            PInt TMP_tmp4_2 = ((PInt)0);
            PMachineValue TMP_tmp5_2 = null;
            PMachineValue TMP_tmp6_2 = null;
            Event TMP_tmp7_2 = null;
            PInt TMP_tmp8_2 = ((PInt)0);
            PInt TMP_tmp9_2 = ((PInt)0);
            PNamedTuple TMP_tmp10_2 = (new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)));
            val_1 = (PInt)(((PInt)(0)));
            TMP_tmp0_2 = (PInt)(((PNamedTuple)req_2)["key"]);
            TMP_tmp1_2 = (PBool)(((PBool)(((PMap)dbStore).ContainsKey(TMP_tmp0_2))));
            if (TMP_tmp1_2)
            {
                TMP_tmp2_2 = (PInt)(((PNamedTuple)req_2)["key"]);
                TMP_tmp3_2 = (PInt)(((PMap)dbStore)[TMP_tmp2_2]);
                TMP_tmp4_2 = (PInt)(((PInt)((IPValue)TMP_tmp3_2)?.Clone()));
                val_1 = TMP_tmp4_2;
            }
            TMP_tmp5_2 = (PMachineValue)(((PNamedTuple)req_2)["lc"]);
            TMP_tmp6_2 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp5_2)?.Clone()));
            TMP_tmp7_2 = (Event)(new eDbRefreshResp((new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)))));
            TMP_tmp8_2 = (PInt)(((PNamedTuple)req_2)["key"]);
            TMP_tmp9_2 = (PInt)(((PInt)((IPValue)val_1)?.Clone()));
            TMP_tmp10_2 = (PNamedTuple)((new PNamedTuple(new string[]{"key","value"}, TMP_tmp8_2, TMP_tmp9_2)));
            TMP_tmp7_2.Payload = TMP_tmp10_2;
            currentMachine.SendEvent(TMP_tmp6_2, (Event)TMP_tmp7_2);
        }
        [Start]
        [OnEventDoAction(typeof(eWrite), nameof(Anon))]
        [OnEventDoAction(typeof(eDbRead), nameof(Anon_1))]
        [OnEventDoAction(typeof(eDbRefresh), nameof(Anon_2))]
        class Ready : State
        {
        }
    }
}
namespace PImplementation
{
    internal partial class LookasideCache : StateMachine
    {
        private PMachineValue db = null;
        private PMap localCache = new PMap();
        private PMap pendingReadClients = new PMap();
        private PSet refreshingKeys = new PSet();
        public class ConstructorEvent : Event{public ConstructorEvent(IPValue val) : base(val) { }}
        
        protected override Event GetConstructorEvent(IPValue value) { return new ConstructorEvent((IPValue)value); }
        public LookasideCache() {
            this.sends.Add(nameof(eDbRead));
            this.sends.Add(nameof(eDbReadResp));
            this.sends.Add(nameof(eDbRefresh));
            this.sends.Add(nameof(eDbRefreshResp));
            this.sends.Add(nameof(eMonitorCacheHit));
            this.sends.Add(nameof(eMonitorDbWrite));
            this.sends.Add(nameof(eRead));
            this.sends.Add(nameof(eReadResp));
            this.sends.Add(nameof(eWrite));
            this.sends.Add(nameof(eWriteResp));
            this.sends.Add(nameof(PHalt));
            this.receives.Add(nameof(eDbRead));
            this.receives.Add(nameof(eDbReadResp));
            this.receives.Add(nameof(eDbRefresh));
            this.receives.Add(nameof(eDbRefreshResp));
            this.receives.Add(nameof(eMonitorCacheHit));
            this.receives.Add(nameof(eMonitorDbWrite));
            this.receives.Add(nameof(eRead));
            this.receives.Add(nameof(eReadResp));
            this.receives.Add(nameof(eWrite));
            this.receives.Add(nameof(eWriteResp));
            this.receives.Add(nameof(PHalt));
        }
        
        public void Anon_3(Event currentMachine_dequeuedEvent)
        {
            LookasideCache currentMachine = this;
            PNamedTuple p = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PMachineValue TMP_tmp0_3 = null;
            PMachineValue TMP_tmp1_3 = null;
            TMP_tmp0_3 = (PMachineValue)(((PNamedTuple)p)["db"]);
            TMP_tmp1_3 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp0_3)?.Clone()));
            db = TMP_tmp1_3;
            currentMachine.RaiseGotoStateEvent<Ready>();
            return;
        }
        public void Anon_4(Event currentMachine_dequeuedEvent)
        {
            LookasideCache currentMachine = this;
            PNamedTuple req_3 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt TMP_tmp0_4 = ((PInt)0);
            PBool TMP_tmp1_4 = ((PBool)false);
            PInt TMP_tmp2_3 = ((PInt)0);
            PInt TMP_tmp3_3 = ((PInt)0);
            PInt TMP_tmp4_3 = ((PInt)0);
            PInt TMP_tmp5_3 = ((PInt)0);
            PNamedTuple TMP_tmp6_3 = (new PNamedTuple(new string[]{"key","value","podId"},((PInt)0), ((PInt)0), ((PInt)0)));
            PMachineValue TMP_tmp7_3 = null;
            PMachineValue TMP_tmp8_3 = null;
            Event TMP_tmp9_3 = null;
            PInt TMP_tmp10_3 = ((PInt)0);
            PInt TMP_tmp11_1 = ((PInt)0);
            PInt TMP_tmp12 = ((PInt)0);
            PNamedTuple TMP_tmp13 = (new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)));
            PInt TMP_tmp14 = ((PInt)0);
            PBool TMP_tmp15 = ((PBool)false);
            PInt TMP_tmp16 = ((PInt)0);
            PInt TMP_tmp17 = ((PInt)0);
            PSeq TMP_tmp18 = new PSeq();
            PInt TMP_tmp19 = ((PInt)0);
            PMachineValue TMP_tmp20 = null;
            PInt TMP_tmp21 = ((PInt)0);
            PSeq TMP_tmp22 = new PSeq();
            PInt TMP_tmp23 = ((PInt)0);
            PMachineValue TMP_tmp24 = null;
            PMachineValue TMP_tmp25 = null;
            Event TMP_tmp26 = null;
            PMachineValue TMP_tmp27 = null;
            PInt TMP_tmp28 = ((PInt)0);
            PNamedTuple TMP_tmp29 = (new PNamedTuple(new string[]{"lc","key"},null, ((PInt)0)));
            TMP_tmp0_4 = (PInt)(((PNamedTuple)req_3)["key"]);
            TMP_tmp1_4 = (PBool)(((PBool)(((PMap)localCache).ContainsKey(TMP_tmp0_4))));
            if (TMP_tmp1_4)
            {
                TMP_tmp2_3 = (PInt)(((PNamedTuple)req_3)["key"]);
                TMP_tmp3_3 = (PInt)(((PNamedTuple)req_3)["key"]);
                TMP_tmp4_3 = (PInt)(((PMap)localCache)[TMP_tmp3_3]);
                TMP_tmp5_3 = (PInt)(((PInt)(0)));
                TMP_tmp6_3 = (PNamedTuple)((new PNamedTuple(new string[]{"key","value","podId"}, TMP_tmp2_3, TMP_tmp4_3, TMP_tmp5_3)));
                currentMachine.Announce((Event)new eMonitorCacheHit((new PNamedTuple(new string[]{"key","value","podId"},((PInt)0), ((PInt)0), ((PInt)0)))), TMP_tmp6_3);
                TMP_tmp7_3 = (PMachineValue)(((PNamedTuple)req_3)["client"]);
                TMP_tmp8_3 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp7_3)?.Clone()));
                TMP_tmp9_3 = (Event)(new eReadResp((new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)))));
                TMP_tmp10_3 = (PInt)(((PNamedTuple)req_3)["key"]);
                TMP_tmp11_1 = (PInt)(((PNamedTuple)req_3)["key"]);
                TMP_tmp12 = (PInt)(((PMap)localCache)[TMP_tmp11_1]);
                TMP_tmp13 = (PNamedTuple)((new PNamedTuple(new string[]{"key","value"}, TMP_tmp10_3, TMP_tmp12)));
                TMP_tmp9_3.Payload = TMP_tmp13;
                currentMachine.SendEvent(TMP_tmp8_3, (Event)TMP_tmp9_3);
            }
            else
            {
                TMP_tmp14 = (PInt)(((PNamedTuple)req_3)["key"]);
                TMP_tmp15 = (PBool)(((PBool)(((PMap)pendingReadClients).ContainsKey(TMP_tmp14))));
                if (TMP_tmp15)
                {
                    TMP_tmp16 = (PInt)(((PNamedTuple)req_3)["key"]);
                    TMP_tmp17 = (PInt)(((PNamedTuple)req_3)["key"]);
                    TMP_tmp18 = (PSeq)(((PMap)pendingReadClients)[TMP_tmp17]);
                    TMP_tmp19 = (PInt)(((PInt)(TMP_tmp18).Count));
                    TMP_tmp20 = (PMachineValue)(((PNamedTuple)req_3)["client"]);
                    ((PSeq)((PMap)pendingReadClients)[TMP_tmp16]).Insert(TMP_tmp19, TMP_tmp20);
                }
                else
                {
                    TMP_tmp21 = (PInt)(((PNamedTuple)req_3)["key"]);
                    TMP_tmp22 = (PSeq)(new PSeq());
                    ((PMap)pendingReadClients)[TMP_tmp21] = TMP_tmp22;
                    TMP_tmp23 = (PInt)(((PNamedTuple)req_3)["key"]);
                    TMP_tmp24 = (PMachineValue)(((PNamedTuple)req_3)["client"]);
                    ((PSeq)((PMap)pendingReadClients)[TMP_tmp23]).Insert(((PInt)(0)), TMP_tmp24);
                    TMP_tmp25 = (PMachineValue)(((PMachineValue)((IPValue)db)?.Clone()));
                    TMP_tmp26 = (Event)(new eDbRead((new PNamedTuple(new string[]{"lc","key"},null, ((PInt)0)))));
                    TMP_tmp27 = (PMachineValue)(currentMachine.self);
                    TMP_tmp28 = (PInt)(((PNamedTuple)req_3)["key"]);
                    TMP_tmp29 = (PNamedTuple)((new PNamedTuple(new string[]{"lc","key"}, TMP_tmp27, TMP_tmp28)));
                    TMP_tmp26.Payload = TMP_tmp29;
                    currentMachine.SendEvent(TMP_tmp25, (Event)TMP_tmp26);
                }
            }
        }
        public void Anon_5(Event currentMachine_dequeuedEvent)
        {
            LookasideCache currentMachine = this;
            PNamedTuple resp = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt i = ((PInt)0);
            PInt k = ((PInt)0);
            PSeq cacheKeys = new PSeq();
            PInt TMP_tmp0_5 = ((PInt)0);
            PInt TMP_tmp1_5 = ((PInt)0);
            PInt TMP_tmp2_4 = ((PInt)0);
            PInt TMP_tmp3_4 = ((PInt)0);
            PSeq TMP_tmp4_4 = new PSeq();
            PInt TMP_tmp5_4 = ((PInt)0);
            PBool TMP_tmp6_4 = ((PBool)false);
            PBool TMP_tmp7_4 = ((PBool)false);
            PInt TMP_tmp8_4 = ((PInt)0);
            PSeq TMP_tmp9_4 = new PSeq();
            PMachineValue TMP_tmp10_4 = null;
            PMachineValue TMP_tmp11_2 = null;
            Event TMP_tmp12_1 = null;
            PInt TMP_tmp13_1 = ((PInt)0);
            PInt TMP_tmp14_1 = ((PInt)0);
            PNamedTuple TMP_tmp15_1 = (new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)));
            PInt TMP_tmp16_1 = ((PInt)0);
            PInt TMP_tmp17_1 = ((PInt)0);
            PBool TMP_tmp18_1 = ((PBool)false);
            PSeq TMP_tmp19_1 = new PSeq();
            PSeq TMP_tmp20_1 = new PSeq();
            PInt TMP_i_k_tmp21 = ((PInt)0);
            PInt sizeof_k_tmp22 = ((PInt)0);
            PInt TMP_tmp23_1 = ((PInt)0);
            PInt TMP_tmp24_1 = ((PInt)0);
            PBool TMP_tmp25_1 = ((PBool)false);
            PBool TMP_tmp26_1 = ((PBool)false);
            PInt TMP_tmp27_1 = ((PInt)0);
            PInt TMP_tmp28_1 = ((PInt)0);
            PInt TMP_tmp29_1 = ((PInt)0);
            PBool TMP_tmp30 = ((PBool)false);
            PBool TMP_tmp31 = ((PBool)false);
            PInt TMP_tmp32 = ((PInt)0);
            PMachineValue TMP_tmp33 = null;
            Event TMP_tmp34 = null;
            PMachineValue TMP_tmp35 = null;
            PInt TMP_tmp36 = ((PInt)0);
            PNamedTuple TMP_tmp37 = (new PNamedTuple(new string[]{"lc","key"},null, ((PInt)0)));
            TMP_tmp0_5 = (PInt)(((PNamedTuple)resp)["key"]);
            TMP_tmp1_5 = (PInt)(((PNamedTuple)resp)["value"]);
            TMP_tmp2_4 = (PInt)(((PInt)((IPValue)TMP_tmp1_5)?.Clone()));
            ((PMap)localCache)[TMP_tmp0_5] = TMP_tmp2_4;
            i = (PInt)(((PInt)(0)));
            while (((PBool)true))
            {
                TMP_tmp3_4 = (PInt)(((PNamedTuple)resp)["key"]);
                TMP_tmp4_4 = (PSeq)(((PMap)pendingReadClients)[TMP_tmp3_4]);
                TMP_tmp5_4 = (PInt)(((PInt)(TMP_tmp4_4).Count));
                TMP_tmp6_4 = (PBool)((i) < (TMP_tmp5_4));
                TMP_tmp7_4 = (PBool)(((PBool)((IPValue)TMP_tmp6_4)?.Clone()));
                if (TMP_tmp7_4)
                {
                }
                else
                {
                    break;
                }
                TMP_tmp8_4 = (PInt)(((PNamedTuple)resp)["key"]);
                TMP_tmp9_4 = (PSeq)(((PMap)pendingReadClients)[TMP_tmp8_4]);
                TMP_tmp10_4 = (PMachineValue)(((PSeq)TMP_tmp9_4)[i]);
                TMP_tmp11_2 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp10_4)?.Clone()));
                TMP_tmp12_1 = (Event)(new eReadResp((new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)))));
                TMP_tmp13_1 = (PInt)(((PNamedTuple)resp)["key"]);
                TMP_tmp14_1 = (PInt)(((PNamedTuple)resp)["value"]);
                TMP_tmp15_1 = (PNamedTuple)((new PNamedTuple(new string[]{"key","value"}, TMP_tmp13_1, TMP_tmp14_1)));
                TMP_tmp12_1.Payload = TMP_tmp15_1;
                currentMachine.SendEvent(TMP_tmp11_2, (Event)TMP_tmp12_1);
                TMP_tmp16_1 = (PInt)((i) + (((PInt)(1))));
                i = TMP_tmp16_1;
            }
            TMP_tmp17_1 = (PInt)(((PNamedTuple)resp)["key"]);
            ((PMap)pendingReadClients).Remove(TMP_tmp17_1);
            TMP_tmp18_1 = (PBool)(((PBool)currentMachine.RandomBoolean()));
            if (TMP_tmp18_1)
            {
                TMP_tmp19_1 = (PSeq)((localCache).CloneKeys());
                cacheKeys = TMP_tmp19_1;
                TMP_tmp20_1 = (PSeq)(((PSeq)((IPValue)cacheKeys)?.Clone()));
                TMP_i_k_tmp21 = (PInt)(((PInt)(-1)));
                TMP_tmp23_1 = (PInt)(((PInt)(TMP_tmp20_1).Count));
                sizeof_k_tmp22 = TMP_tmp23_1;
                while (((PBool)true))
                {
                    TMP_tmp24_1 = (PInt)((sizeof_k_tmp22) - (((PInt)(1))));
                    TMP_tmp25_1 = (PBool)((TMP_i_k_tmp21) < (TMP_tmp24_1));
                    TMP_tmp26_1 = (PBool)(((PBool)((IPValue)TMP_tmp25_1)?.Clone()));
                    if (TMP_tmp26_1)
                    {
                    }
                    else
                    {
                        break;
                    }
                    TMP_tmp27_1 = (PInt)((TMP_i_k_tmp21) + (((PInt)(1))));
                    TMP_i_k_tmp21 = TMP_tmp27_1;
                    TMP_tmp28_1 = (PInt)(((PSeq)TMP_tmp20_1)[TMP_i_k_tmp21]);
                    TMP_tmp29_1 = (PInt)(((PInt)((IPValue)TMP_tmp28_1)?.Clone()));
                    k = TMP_tmp29_1;
                    TMP_tmp30 = (PBool)(((PBool)(((PSet)refreshingKeys).Contains(k))));
                    TMP_tmp31 = (PBool)(!(TMP_tmp30));
                    if (TMP_tmp31)
                    {
                        TMP_tmp32 = (PInt)(((PInt)((IPValue)k)?.Clone()));
                        ((PSet)refreshingKeys).Add(TMP_tmp32);
                        TMP_tmp33 = (PMachineValue)(((PMachineValue)((IPValue)db)?.Clone()));
                        TMP_tmp34 = (Event)(new eDbRefresh((new PNamedTuple(new string[]{"lc","key"},null, ((PInt)0)))));
                        TMP_tmp35 = (PMachineValue)(currentMachine.self);
                        TMP_tmp36 = (PInt)(((PInt)((IPValue)k)?.Clone()));
                        TMP_tmp37 = (PNamedTuple)((new PNamedTuple(new string[]{"lc","key"}, TMP_tmp35, TMP_tmp36)));
                        TMP_tmp34.Payload = TMP_tmp37;
                        currentMachine.SendEvent(TMP_tmp33, (Event)TMP_tmp34);
                    }
                }
            }
        }
        public void Anon_6(Event currentMachine_dequeuedEvent)
        {
            LookasideCache currentMachine = this;
            PNamedTuple resp_1 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt TMP_tmp0_6 = ((PInt)0);
            PInt TMP_tmp1_6 = ((PInt)0);
            PInt TMP_tmp2_5 = ((PInt)0);
            PInt TMP_tmp3_5 = ((PInt)0);
            TMP_tmp0_6 = (PInt)(((PNamedTuple)resp_1)["key"]);
            TMP_tmp1_6 = (PInt)(((PNamedTuple)resp_1)["value"]);
            TMP_tmp2_5 = (PInt)(((PInt)((IPValue)TMP_tmp1_6)?.Clone()));
            ((PMap)localCache)[TMP_tmp0_6] = TMP_tmp2_5;
            TMP_tmp3_5 = (PInt)(((PNamedTuple)resp_1)["key"]);
            ((PSet)refreshingKeys).Remove(TMP_tmp3_5);
        }
        [Start]
        [OnEntry(nameof(Anon_3))]
        class Init : State
        {
        }
        [OnEventDoAction(typeof(eRead), nameof(Anon_4))]
        [OnEventDoAction(typeof(eDbReadResp), nameof(Anon_5))]
        [OnEventDoAction(typeof(eDbRefreshResp), nameof(Anon_6))]
        class Ready : State
        {
        }
    }
}
namespace PImplementation
{
    internal partial class LSISafety : Monitor
    {
        private PMap storageState = new PMap();
        static LSISafety() {
            observes.Add(nameof(eMonitorCacheHit));
            observes.Add(nameof(eMonitorDbWrite));
        }
        
        public void Anon_7(Event currentMachine_dequeuedEvent)
        {
            LSISafety currentMachine = this;
            PNamedTuple payload = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt TMP_tmp0_7 = ((PInt)0);
            PInt TMP_tmp1_7 = ((PInt)0);
            PInt TMP_tmp2_6 = ((PInt)0);
            TMP_tmp0_7 = (PInt)(((PNamedTuple)payload)["key"]);
            TMP_tmp1_7 = (PInt)(((PNamedTuple)payload)["value"]);
            TMP_tmp2_6 = (PInt)(((PInt)((IPValue)TMP_tmp1_7)?.Clone()));
            ((PMap)storageState)[TMP_tmp0_7] = TMP_tmp2_6;
        }
        public void Anon_8(Event currentMachine_dequeuedEvent)
        {
            LSISafety currentMachine = this;
            PNamedTuple payload_1 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt expected = ((PInt)0);
            PInt TMP_tmp0_8 = ((PInt)0);
            PBool TMP_tmp1_8 = ((PBool)false);
            PInt TMP_tmp2_7 = ((PInt)0);
            PInt TMP_tmp3_6 = ((PInt)0);
            PInt TMP_tmp4_5 = ((PInt)0);
            PInt TMP_tmp5_5 = ((PInt)0);
            PBool TMP_tmp6_5 = ((PBool)false);
            PString TMP_tmp7_5 = ((PString)"");
            PInt TMP_tmp8_5 = ((PInt)0);
            PInt TMP_tmp9_5 = ((PInt)0);
            PInt TMP_tmp10_5 = ((PInt)0);
            PInt TMP_tmp11_3 = ((PInt)0);
            PString TMP_tmp12_2 = ((PString)"");
            PString TMP_tmp13_2 = ((PString)"");
            expected = (PInt)(((PInt)(0)));
            TMP_tmp0_8 = (PInt)(((PNamedTuple)payload_1)["key"]);
            TMP_tmp1_8 = (PBool)(((PBool)(((PMap)storageState).ContainsKey(TMP_tmp0_8))));
            if (TMP_tmp1_8)
            {
                TMP_tmp2_7 = (PInt)(((PNamedTuple)payload_1)["key"]);
                TMP_tmp3_6 = (PInt)(((PMap)storageState)[TMP_tmp2_7]);
                TMP_tmp4_5 = (PInt)(((PInt)((IPValue)TMP_tmp3_6)?.Clone()));
                expected = TMP_tmp4_5;
            }
            TMP_tmp5_5 = (PInt)(((PNamedTuple)payload_1)["value"]);
            TMP_tmp6_5 = (PBool)((PValues.SafeEquals(TMP_tmp5_5,expected)));
            if (TMP_tmp6_5)
            {
            }
            else
            {
                TMP_tmp7_5 = (PString)(((PString) String.Format("PSpec/Spec.p:18:13")));
                TMP_tmp8_5 = (PInt)(((PNamedTuple)payload_1)["podId"]);
                TMP_tmp9_5 = (PInt)(((PNamedTuple)payload_1)["key"]);
                TMP_tmp10_5 = (PInt)(((PNamedTuple)payload_1)["value"]);
                TMP_tmp11_3 = (PInt)(((PInt)((IPValue)expected)?.Clone()));
                TMP_tmp12_2 = (PString)(((PString) String.Format("LSI VIOLATION: cache {0} hit key={1} returned {2} but storage has {3}",TMP_tmp8_5,TMP_tmp9_5,TMP_tmp10_5,TMP_tmp11_3)));
                TMP_tmp13_2 = (PString)(((PString) String.Format("{0} {1}",TMP_tmp7_5,TMP_tmp12_2)));
                currentMachine.Assert(TMP_tmp6_5,"Assertion Failed: " + TMP_tmp13_2);
            }
        }
        [Start]
        [OnEventDoAction(typeof(eMonitorDbWrite), nameof(Anon_7))]
        [OnEventDoAction(typeof(eMonitorCacheHit), nameof(Anon_8))]
        class Watching : State
        {
        }
    }
}
namespace PImplementation
{
    internal partial class Client : StateMachine
    {
        private PMachineValue cache = null;
        private PMachineValue db_1 = null;
        private PInt clientId = ((PInt)0);
        private PInt numOps = ((PInt)0);
        private PInt opsIssued = ((PInt)0);
        public class ConstructorEvent : Event{public ConstructorEvent(IPValue val) : base(val) { }}
        
        protected override Event GetConstructorEvent(IPValue value) { return new ConstructorEvent((IPValue)value); }
        public Client() {
            this.sends.Add(nameof(eDbRead));
            this.sends.Add(nameof(eDbReadResp));
            this.sends.Add(nameof(eDbRefresh));
            this.sends.Add(nameof(eDbRefreshResp));
            this.sends.Add(nameof(eMonitorCacheHit));
            this.sends.Add(nameof(eMonitorDbWrite));
            this.sends.Add(nameof(eRead));
            this.sends.Add(nameof(eReadResp));
            this.sends.Add(nameof(eWrite));
            this.sends.Add(nameof(eWriteResp));
            this.sends.Add(nameof(PHalt));
            this.receives.Add(nameof(eDbRead));
            this.receives.Add(nameof(eDbReadResp));
            this.receives.Add(nameof(eDbRefresh));
            this.receives.Add(nameof(eDbRefreshResp));
            this.receives.Add(nameof(eMonitorCacheHit));
            this.receives.Add(nameof(eMonitorDbWrite));
            this.receives.Add(nameof(eRead));
            this.receives.Add(nameof(eReadResp));
            this.receives.Add(nameof(eWrite));
            this.receives.Add(nameof(eWriteResp));
            this.receives.Add(nameof(PHalt));
        }
        
        public void Anon_9(Event currentMachine_dequeuedEvent)
        {
            Client currentMachine = this;
            PNamedTuple p_1 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PMachineValue TMP_tmp0_9 = null;
            PMachineValue TMP_tmp1_9 = null;
            PMachineValue TMP_tmp2_8 = null;
            PMachineValue TMP_tmp3_7 = null;
            PInt TMP_tmp4_6 = ((PInt)0);
            PInt TMP_tmp5_6 = ((PInt)0);
            PInt TMP_tmp6_6 = ((PInt)0);
            PInt TMP_tmp7_6 = ((PInt)0);
            TMP_tmp0_9 = (PMachineValue)(((PNamedTuple)p_1)["cache"]);
            TMP_tmp1_9 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp0_9)?.Clone()));
            cache = TMP_tmp1_9;
            TMP_tmp2_8 = (PMachineValue)(((PNamedTuple)p_1)["db"]);
            TMP_tmp3_7 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp2_8)?.Clone()));
            db_1 = TMP_tmp3_7;
            TMP_tmp4_6 = (PInt)(((PNamedTuple)p_1)["id"]);
            TMP_tmp5_6 = (PInt)(((PInt)((IPValue)TMP_tmp4_6)?.Clone()));
            clientId = TMP_tmp5_6;
            TMP_tmp6_6 = (PInt)(((PNamedTuple)p_1)["numOps"]);
            TMP_tmp7_6 = (PInt)(((PInt)((IPValue)TMP_tmp6_6)?.Clone()));
            numOps = TMP_tmp7_6;
            opsIssued = (PInt)(((PInt)(0)));
            currentMachine.RaiseGotoStateEvent<Issuing>();
            return;
        }
        public void Anon_10(Event currentMachine_dequeuedEvent)
        {
            Client currentMachine = this;
            PInt key = ((PInt)0);
            PBool TMP_tmp0_10 = ((PBool)false);
            PInt TMP_tmp1_10 = ((PInt)0);
            PInt TMP_tmp2_9 = ((PInt)0);
            PBool TMP_tmp3_8 = ((PBool)false);
            PInt TMP_tmp4_7 = ((PInt)0);
            PInt TMP_tmp5_7 = ((PInt)0);
            PString TMP_tmp6_7 = ((PString)"");
            PMachineValue TMP_tmp7_7 = null;
            Event TMP_tmp8_6 = null;
            PMachineValue TMP_tmp9_6 = null;
            PInt TMP_tmp10_6 = ((PInt)0);
            PNamedTuple TMP_tmp11_4 = (new PNamedTuple(new string[]{"client","key"},null, ((PInt)0)));
            PInt TMP_tmp12_3 = ((PInt)0);
            PInt TMP_tmp13_3 = ((PInt)0);
            PInt TMP_tmp14_2 = ((PInt)0);
            PInt TMP_tmp15_2 = ((PInt)0);
            PString TMP_tmp16_2 = ((PString)"");
            PMachineValue TMP_tmp17_2 = null;
            Event TMP_tmp18_2 = null;
            PMachineValue TMP_tmp19_2 = null;
            PInt TMP_tmp20_2 = ((PInt)0);
            PInt TMP_tmp21_1 = ((PInt)0);
            PInt TMP_tmp22_1 = ((PInt)0);
            PNamedTuple TMP_tmp23_2 = (new PNamedTuple(new string[]{"client","key","value"},null, ((PInt)0), ((PInt)0)));
            PInt TMP_tmp24_2 = ((PInt)0);
            TMP_tmp0_10 = (PBool)((opsIssued) >= (numOps));
            if (TMP_tmp0_10)
            {
                currentMachine.RaiseGotoStateEvent<Done>();
                return;
                return ;
            }
            TMP_tmp1_10 = (PInt)(((PInt)currentMachine.TryRandom(((PInt)(3)))));
            TMP_tmp2_9 = (PInt)((((PInt)(40))) + (TMP_tmp1_10));
            key = TMP_tmp2_9;
            TMP_tmp3_8 = (PBool)(((PBool)currentMachine.RandomBoolean()));
            if (TMP_tmp3_8)
            {
                TMP_tmp4_7 = (PInt)(((PInt)((IPValue)clientId)?.Clone()));
                TMP_tmp5_7 = (PInt)(((PInt)((IPValue)key)?.Clone()));
                TMP_tmp6_7 = (PString)(((PString) String.Format("Client {0}: READ  key={1}",TMP_tmp4_7,TMP_tmp5_7)));
                currentMachine.LogLine("" + TMP_tmp6_7);
                TMP_tmp7_7 = (PMachineValue)(((PMachineValue)((IPValue)cache)?.Clone()));
                TMP_tmp8_6 = (Event)(new eRead((new PNamedTuple(new string[]{"client","key"},null, ((PInt)0)))));
                TMP_tmp9_6 = (PMachineValue)(currentMachine.self);
                TMP_tmp10_6 = (PInt)(((PInt)((IPValue)key)?.Clone()));
                TMP_tmp11_4 = (PNamedTuple)((new PNamedTuple(new string[]{"client","key"}, TMP_tmp9_6, TMP_tmp10_6)));
                TMP_tmp8_6.Payload = TMP_tmp11_4;
                currentMachine.SendEvent(TMP_tmp7_7, (Event)TMP_tmp8_6);
            }
            else
            {
                TMP_tmp12_3 = (PInt)(((PInt)((IPValue)clientId)?.Clone()));
                TMP_tmp13_3 = (PInt)(((PInt)((IPValue)key)?.Clone()));
                TMP_tmp14_2 = (PInt)((clientId) * (((PInt)(100))));
                TMP_tmp15_2 = (PInt)((TMP_tmp14_2) + (opsIssued));
                TMP_tmp16_2 = (PString)(((PString) String.Format("Client {0}: WRITE key={1} val={2}",TMP_tmp12_3,TMP_tmp13_3,TMP_tmp15_2)));
                currentMachine.LogLine("" + TMP_tmp16_2);
                TMP_tmp17_2 = (PMachineValue)(((PMachineValue)((IPValue)db_1)?.Clone()));
                TMP_tmp18_2 = (Event)(new eWrite((new PNamedTuple(new string[]{"client","key","value"},null, ((PInt)0), ((PInt)0)))));
                TMP_tmp19_2 = (PMachineValue)(currentMachine.self);
                TMP_tmp20_2 = (PInt)(((PInt)((IPValue)key)?.Clone()));
                TMP_tmp21_1 = (PInt)((clientId) * (((PInt)(100))));
                TMP_tmp22_1 = (PInt)((TMP_tmp21_1) + (opsIssued));
                TMP_tmp23_2 = (PNamedTuple)((new PNamedTuple(new string[]{"client","key","value"}, TMP_tmp19_2, TMP_tmp20_2, TMP_tmp22_1)));
                TMP_tmp18_2.Payload = TMP_tmp23_2;
                currentMachine.SendEvent(TMP_tmp17_2, (Event)TMP_tmp18_2);
            }
            TMP_tmp24_2 = (PInt)((opsIssued) + (((PInt)(1))));
            opsIssued = TMP_tmp24_2;
        }
        public void Anon_11(Event currentMachine_dequeuedEvent)
        {
            Client currentMachine = this;
            PNamedTuple resp_2 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            currentMachine.RaiseGotoStateEvent<Issuing>();
            return;
        }
        public void Anon_12(Event currentMachine_dequeuedEvent)
        {
            Client currentMachine = this;
            PNamedTuple resp_3 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            currentMachine.RaiseGotoStateEvent<Issuing>();
            return;
        }
        [Start]
        [OnEntry(nameof(Anon_9))]
        class Init : State
        {
        }
        [OnEntry(nameof(Anon_10))]
        [OnEventDoAction(typeof(eReadResp), nameof(Anon_11))]
        [OnEventDoAction(typeof(eWriteResp), nameof(Anon_12))]
        class Issuing : State
        {
        }
        [IgnoreEvents(typeof(eReadResp), typeof(eWriteResp))]
        class Done : State
        {
        }
    }
}
namespace PImplementation
{
    internal partial class TestDriver : StateMachine
    {
        private PMachineValue db_2 = null;
        private PMachineValue cache_1 = null;
        private PMachineValue client0 = null;
        private PMachineValue client1 = null;
        public class ConstructorEvent : Event{public ConstructorEvent(IPValue val) : base(val) { }}
        
        protected override Event GetConstructorEvent(IPValue value) { return new ConstructorEvent((IPValue)value); }
        public TestDriver() {
            this.sends.Add(nameof(eDbRead));
            this.sends.Add(nameof(eDbReadResp));
            this.sends.Add(nameof(eDbRefresh));
            this.sends.Add(nameof(eDbRefreshResp));
            this.sends.Add(nameof(eMonitorCacheHit));
            this.sends.Add(nameof(eMonitorDbWrite));
            this.sends.Add(nameof(eRead));
            this.sends.Add(nameof(eReadResp));
            this.sends.Add(nameof(eWrite));
            this.sends.Add(nameof(eWriteResp));
            this.sends.Add(nameof(PHalt));
            this.receives.Add(nameof(eDbRead));
            this.receives.Add(nameof(eDbReadResp));
            this.receives.Add(nameof(eDbRefresh));
            this.receives.Add(nameof(eDbRefreshResp));
            this.receives.Add(nameof(eMonitorCacheHit));
            this.receives.Add(nameof(eMonitorDbWrite));
            this.receives.Add(nameof(eRead));
            this.receives.Add(nameof(eReadResp));
            this.receives.Add(nameof(eWrite));
            this.receives.Add(nameof(eWriteResp));
            this.receives.Add(nameof(PHalt));
            this.creates.Add(nameof(I_Client));
            this.creates.Add(nameof(I_LookasideCache));
            this.creates.Add(nameof(I_SimpleTiDB));
        }
        
        public void Anon_13(Event currentMachine_dequeuedEvent)
        {
            TestDriver currentMachine = this;
            PMachineValue TMP_tmp0_11 = null;
            PMachineValue TMP_tmp1_11 = null;
            PNamedTuple TMP_tmp2_10 = (new PNamedTuple(new string[]{"db"},null));
            PMachineValue TMP_tmp3_9 = null;
            PMachineValue TMP_tmp4_8 = null;
            PMachineValue TMP_tmp5_8 = null;
            PInt TMP_tmp6_8 = ((PInt)0);
            PInt TMP_tmp7_8 = ((PInt)0);
            PNamedTuple TMP_tmp8_7 = (new PNamedTuple(new string[]{"cache","db","id","numOps"},null, null, ((PInt)0), ((PInt)0)));
            PMachineValue TMP_tmp9_7 = null;
            PMachineValue TMP_tmp10_7 = null;
            PMachineValue TMP_tmp11_5 = null;
            PInt TMP_tmp12_4 = ((PInt)0);
            PInt TMP_tmp13_4 = ((PInt)0);
            PNamedTuple TMP_tmp14_3 = (new PNamedTuple(new string[]{"cache","db","id","numOps"},null, null, ((PInt)0), ((PInt)0)));
            PMachineValue TMP_tmp15_3 = null;
            TMP_tmp0_11 = (PMachineValue)(currentMachine.CreateInterface<I_SimpleTiDB>( currentMachine));
            db_2 = (PMachineValue)TMP_tmp0_11;
            TMP_tmp1_11 = (PMachineValue)(((PMachineValue)((IPValue)db_2)?.Clone()));
            TMP_tmp2_10 = (PNamedTuple)((new PNamedTuple(new string[]{"db"}, TMP_tmp1_11)));
            TMP_tmp3_9 = (PMachineValue)(currentMachine.CreateInterface<I_LookasideCache>( currentMachine, TMP_tmp2_10));
            cache_1 = (PMachineValue)TMP_tmp3_9;
            TMP_tmp4_8 = (PMachineValue)(((PMachineValue)((IPValue)cache_1)?.Clone()));
            TMP_tmp5_8 = (PMachineValue)(((PMachineValue)((IPValue)db_2)?.Clone()));
            TMP_tmp6_8 = (PInt)(((PInt)(0)));
            TMP_tmp7_8 = (PInt)(((PInt)(20)));
            TMP_tmp8_7 = (PNamedTuple)((new PNamedTuple(new string[]{"cache","db","id","numOps"}, TMP_tmp4_8, TMP_tmp5_8, TMP_tmp6_8, TMP_tmp7_8)));
            TMP_tmp9_7 = (PMachineValue)(currentMachine.CreateInterface<I_Client>( currentMachine, TMP_tmp8_7));
            client0 = (PMachineValue)TMP_tmp9_7;
            TMP_tmp10_7 = (PMachineValue)(((PMachineValue)((IPValue)cache_1)?.Clone()));
            TMP_tmp11_5 = (PMachineValue)(((PMachineValue)((IPValue)db_2)?.Clone()));
            TMP_tmp12_4 = (PInt)(((PInt)(1)));
            TMP_tmp13_4 = (PInt)(((PInt)(20)));
            TMP_tmp14_3 = (PNamedTuple)((new PNamedTuple(new string[]{"cache","db","id","numOps"}, TMP_tmp10_7, TMP_tmp11_5, TMP_tmp12_4, TMP_tmp13_4)));
            TMP_tmp15_3 = (PMachineValue)(currentMachine.CreateInterface<I_Client>( currentMachine, TMP_tmp14_3));
            client1 = (PMachineValue)TMP_tmp15_3;
            currentMachine.RaiseGotoStateEvent<Done>();
            return;
        }
        [Start]
        [OnEntry(nameof(Anon_13))]
        class Init : State
        {
        }
        class Done : State
        {
        }
    }
}
namespace PImplementation
{
    public class tcLookasideLSI {
        public static void InitializeGlobalParams() {
        }
        public static void InitializeLinkMap() {
            PModule.linkMap.Clear();
            PModule.linkMap[nameof(I_TestDriver)] = new Dictionary<string, string>();
            PModule.linkMap[nameof(I_TestDriver)].Add(nameof(I_Client), nameof(I_Client));
            PModule.linkMap[nameof(I_TestDriver)].Add(nameof(I_LookasideCache), nameof(I_LookasideCache));
            PModule.linkMap[nameof(I_TestDriver)].Add(nameof(I_SimpleTiDB), nameof(I_SimpleTiDB));
            PModule.linkMap[nameof(I_SimpleTiDB)] = new Dictionary<string, string>();
            PModule.linkMap[nameof(I_LookasideCache)] = new Dictionary<string, string>();
            PModule.linkMap[nameof(I_Client)] = new Dictionary<string, string>();
        }
        
        public static void InitializeInterfaceDefMap() {
            PModule.interfaceDefinitionMap.Clear();
            PModule.interfaceDefinitionMap.Add(nameof(I_TestDriver), typeof(TestDriver));
            PModule.interfaceDefinitionMap.Add(nameof(I_SimpleTiDB), typeof(SimpleTiDB));
            PModule.interfaceDefinitionMap.Add(nameof(I_LookasideCache), typeof(LookasideCache));
            PModule.interfaceDefinitionMap.Add(nameof(I_Client), typeof(Client));
        }
        
        public static void InitializeMonitorObserves() {
            PModule.monitorObserves.Clear();
            PModule.monitorObserves[nameof(LSISafety)] = new List<string>();
            PModule.monitorObserves[nameof(LSISafety)].Add(nameof(eMonitorCacheHit));
            PModule.monitorObserves[nameof(LSISafety)].Add(nameof(eMonitorDbWrite));
        }
        
        public static void InitializeMonitorMap(ControlledRuntime runtime) {
            PModule.monitorMap.Clear();
            PModule.monitorMap[nameof(I_TestDriver)] = new List<Type>();
            PModule.monitorMap[nameof(I_TestDriver)].Add(typeof(LSISafety));
            PModule.monitorMap[nameof(I_SimpleTiDB)] = new List<Type>();
            PModule.monitorMap[nameof(I_SimpleTiDB)].Add(typeof(LSISafety));
            PModule.monitorMap[nameof(I_LookasideCache)] = new List<Type>();
            PModule.monitorMap[nameof(I_LookasideCache)].Add(typeof(LSISafety));
            PModule.monitorMap[nameof(I_Client)] = new List<Type>();
            PModule.monitorMap[nameof(I_Client)].Add(typeof(LSISafety));
            runtime.RegisterMonitor<LSISafety>();
        }
        
        
        [PChecker.SystematicTesting.Test]
        public static void Execute(ControlledRuntime runtime) {
            InitializeGlobalParams();
            runtime.RegisterLog(new PCheckerLogTextFormatter());
            runtime.RegisterLog(new PCheckerLogJsonFormatter());
            PModule.runtime = runtime;
            PHelper.InitializeInterfaces();
            PHelper.InitializeEnums();
            InitializeLinkMap();
            InitializeInterfaceDefMap();
            InitializeMonitorMap(runtime);
            InitializeMonitorObserves();
            runtime.CreateStateMachine(typeof(TestDriver), "TestDriver");
        }
    }
}
namespace PImplementation
{
    public class I_SimpleTiDB : PMachineValue {
        public I_SimpleTiDB (StateMachineId machine, List<string> permissions) : base(machine, permissions) { }
    }
    
    public class I_LookasideCache : PMachineValue {
        public I_LookasideCache (StateMachineId machine, List<string> permissions) : base(machine, permissions) { }
    }
    
    public class I_Client : PMachineValue {
        public I_Client (StateMachineId machine, List<string> permissions) : base(machine, permissions) { }
    }
    
    public class I_TestDriver : PMachineValue {
        public I_TestDriver (StateMachineId machine, List<string> permissions) : base(machine, permissions) { }
    }
    
    public partial class PHelper {
        public static void InitializeInterfaces() {
            PInterfaces.Clear();
            PInterfaces.AddInterface(nameof(I_SimpleTiDB), nameof(eDbRead), nameof(eDbReadResp), nameof(eDbRefresh), nameof(eDbRefreshResp), nameof(eMonitorCacheHit), nameof(eMonitorDbWrite), nameof(eRead), nameof(eReadResp), nameof(eWrite), nameof(eWriteResp), nameof(PHalt));
            PInterfaces.AddInterface(nameof(I_LookasideCache), nameof(eDbRead), nameof(eDbReadResp), nameof(eDbRefresh), nameof(eDbRefreshResp), nameof(eMonitorCacheHit), nameof(eMonitorDbWrite), nameof(eRead), nameof(eReadResp), nameof(eWrite), nameof(eWriteResp), nameof(PHalt));
            PInterfaces.AddInterface(nameof(I_Client), nameof(eDbRead), nameof(eDbReadResp), nameof(eDbRefresh), nameof(eDbRefreshResp), nameof(eMonitorCacheHit), nameof(eMonitorDbWrite), nameof(eRead), nameof(eReadResp), nameof(eWrite), nameof(eWriteResp), nameof(PHalt));
            PInterfaces.AddInterface(nameof(I_TestDriver), nameof(eDbRead), nameof(eDbReadResp), nameof(eDbRefresh), nameof(eDbRefreshResp), nameof(eMonitorCacheHit), nameof(eMonitorDbWrite), nameof(eRead), nameof(eReadResp), nameof(eWrite), nameof(eWriteResp), nameof(PHalt));
        }
    }
    
}
namespace PImplementation
{
    public partial class PHelper {
        public static void InitializeEnums() {
            PEnum.Clear();
        }
    }
    
}
#pragma warning restore 162, 219, 414
