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
    internal partial class eWrite : Event
    {
        public eWrite() : base() {}
        public eWrite (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eWrite();}
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
    internal partial class eWriteResp : Event
    {
        public eWriteResp() : base() {}
        public eWriteResp (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eWriteResp();}
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
    internal partial class eMonitorDirectRead : Event
    {
        public eMonitorDirectRead() : base() {}
        public eMonitorDirectRead (PNamedTuple payload): base(payload){ }
        public override IPValue Clone() { return new eMonitorDirectRead();}
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
            this.sends.Add(nameof(eMonitorDbWrite));
            this.sends.Add(nameof(eMonitorDirectRead));
            this.sends.Add(nameof(eRead));
            this.sends.Add(nameof(eReadResp));
            this.sends.Add(nameof(eWrite));
            this.sends.Add(nameof(eWriteResp));
            this.sends.Add(nameof(PHalt));
            this.receives.Add(nameof(eMonitorDbWrite));
            this.receives.Add(nameof(eMonitorDirectRead));
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
            PInt val = ((PInt)0);
            PInt TMP_tmp0 = ((PInt)0);
            PBool TMP_tmp1 = ((PBool)false);
            PInt TMP_tmp2 = ((PInt)0);
            PInt TMP_tmp3 = ((PInt)0);
            PInt TMP_tmp4 = ((PInt)0);
            PInt TMP_tmp5 = ((PInt)0);
            PInt TMP_tmp6 = ((PInt)0);
            PNamedTuple TMP_tmp7 = (new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)));
            PMachineValue TMP_tmp8 = null;
            PMachineValue TMP_tmp9 = null;
            Event TMP_tmp10 = null;
            PInt TMP_tmp11 = ((PInt)0);
            PInt TMP_tmp12 = ((PInt)0);
            PNamedTuple TMP_tmp13 = (new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)));
            val = (PInt)(((PInt)(0)));
            TMP_tmp0 = (PInt)(((PNamedTuple)req)["key"]);
            TMP_tmp1 = (PBool)(((PBool)(((PMap)dbStore).ContainsKey(TMP_tmp0))));
            if (TMP_tmp1)
            {
                TMP_tmp2 = (PInt)(((PNamedTuple)req)["key"]);
                TMP_tmp3 = (PInt)(((PMap)dbStore)[TMP_tmp2]);
                TMP_tmp4 = (PInt)(((PInt)((IPValue)TMP_tmp3)?.Clone()));
                val = TMP_tmp4;
            }
            TMP_tmp5 = (PInt)(((PNamedTuple)req)["key"]);
            TMP_tmp6 = (PInt)(((PInt)((IPValue)val)?.Clone()));
            TMP_tmp7 = (PNamedTuple)((new PNamedTuple(new string[]{"key","value"}, TMP_tmp5, TMP_tmp6)));
            currentMachine.Announce((Event)new eMonitorDirectRead((new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)))), TMP_tmp7);
            TMP_tmp8 = (PMachineValue)(((PNamedTuple)req)["client"]);
            TMP_tmp9 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp8)?.Clone()));
            TMP_tmp10 = (Event)(new eReadResp((new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)))));
            TMP_tmp11 = (PInt)(((PNamedTuple)req)["key"]);
            TMP_tmp12 = (PInt)(((PInt)((IPValue)val)?.Clone()));
            TMP_tmp13 = (PNamedTuple)((new PNamedTuple(new string[]{"key","value"}, TMP_tmp11, TMP_tmp12)));
            TMP_tmp10.Payload = TMP_tmp13;
            currentMachine.SendEvent(TMP_tmp9, (Event)TMP_tmp10);
        }
        public void Anon_1(Event currentMachine_dequeuedEvent)
        {
            SimpleTiDB currentMachine = this;
            PNamedTuple req_1 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt TMP_tmp0_1 = ((PInt)0);
            PInt TMP_tmp1_1 = ((PInt)0);
            PInt TMP_tmp2_1 = ((PInt)0);
            PInt TMP_tmp3_1 = ((PInt)0);
            PInt TMP_tmp4_1 = ((PInt)0);
            PNamedTuple TMP_tmp5_1 = (new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)));
            PMachineValue TMP_tmp6_1 = null;
            PMachineValue TMP_tmp7_1 = null;
            Event TMP_tmp8_1 = null;
            PInt TMP_tmp9_1 = ((PInt)0);
            PBool TMP_tmp10_1 = ((PBool)false);
            PNamedTuple TMP_tmp11_1 = (new PNamedTuple(new string[]{"key","success"},((PInt)0), ((PBool)false)));
            TMP_tmp0_1 = (PInt)(((PNamedTuple)req_1)["key"]);
            TMP_tmp1_1 = (PInt)(((PNamedTuple)req_1)["value"]);
            TMP_tmp2_1 = (PInt)(((PInt)((IPValue)TMP_tmp1_1)?.Clone()));
            ((PMap)dbStore)[TMP_tmp0_1] = TMP_tmp2_1;
            TMP_tmp3_1 = (PInt)(((PNamedTuple)req_1)["key"]);
            TMP_tmp4_1 = (PInt)(((PNamedTuple)req_1)["value"]);
            TMP_tmp5_1 = (PNamedTuple)((new PNamedTuple(new string[]{"key","value"}, TMP_tmp3_1, TMP_tmp4_1)));
            currentMachine.Announce((Event)new eMonitorDbWrite((new PNamedTuple(new string[]{"key","value"},((PInt)0), ((PInt)0)))), TMP_tmp5_1);
            TMP_tmp6_1 = (PMachineValue)(((PNamedTuple)req_1)["client"]);
            TMP_tmp7_1 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp6_1)?.Clone()));
            TMP_tmp8_1 = (Event)(new eWriteResp((new PNamedTuple(new string[]{"key","success"},((PInt)0), ((PBool)false)))));
            TMP_tmp9_1 = (PInt)(((PNamedTuple)req_1)["key"]);
            TMP_tmp10_1 = (PBool)(((PBool)true));
            TMP_tmp11_1 = (PNamedTuple)((new PNamedTuple(new string[]{"key","success"}, TMP_tmp9_1, TMP_tmp10_1)));
            TMP_tmp8_1.Payload = TMP_tmp11_1;
            currentMachine.SendEvent(TMP_tmp7_1, (Event)TMP_tmp8_1);
        }
        [Start]
        [OnEventDoAction(typeof(eRead), nameof(Anon))]
        [OnEventDoAction(typeof(eWrite), nameof(Anon_1))]
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
            observes.Add(nameof(eMonitorDbWrite));
            observes.Add(nameof(eMonitorDirectRead));
        }
        
        public void Anon_2(Event currentMachine_dequeuedEvent)
        {
            LSISafety currentMachine = this;
            PNamedTuple payload = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt TMP_tmp0_2 = ((PInt)0);
            PInt TMP_tmp1_2 = ((PInt)0);
            PInt TMP_tmp2_2 = ((PInt)0);
            TMP_tmp0_2 = (PInt)(((PNamedTuple)payload)["key"]);
            TMP_tmp1_2 = (PInt)(((PNamedTuple)payload)["value"]);
            TMP_tmp2_2 = (PInt)(((PInt)((IPValue)TMP_tmp1_2)?.Clone()));
            ((PMap)storageState)[TMP_tmp0_2] = TMP_tmp2_2;
        }
        public void Anon_3(Event currentMachine_dequeuedEvent)
        {
            LSISafety currentMachine = this;
            PNamedTuple payload_1 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PInt expected = ((PInt)0);
            PInt TMP_tmp0_3 = ((PInt)0);
            PBool TMP_tmp1_3 = ((PBool)false);
            PInt TMP_tmp2_3 = ((PInt)0);
            PInt TMP_tmp3_2 = ((PInt)0);
            PInt TMP_tmp4_2 = ((PInt)0);
            PInt TMP_tmp5_2 = ((PInt)0);
            PBool TMP_tmp6_2 = ((PBool)false);
            PString TMP_tmp7_2 = ((PString)"");
            PInt TMP_tmp8_2 = ((PInt)0);
            PInt TMP_tmp9_2 = ((PInt)0);
            PInt TMP_tmp10_2 = ((PInt)0);
            PString TMP_tmp11_2 = ((PString)"");
            PString TMP_tmp12_1 = ((PString)"");
            expected = (PInt)(((PInt)(0)));
            TMP_tmp0_3 = (PInt)(((PNamedTuple)payload_1)["key"]);
            TMP_tmp1_3 = (PBool)(((PBool)(((PMap)storageState).ContainsKey(TMP_tmp0_3))));
            if (TMP_tmp1_3)
            {
                TMP_tmp2_3 = (PInt)(((PNamedTuple)payload_1)["key"]);
                TMP_tmp3_2 = (PInt)(((PMap)storageState)[TMP_tmp2_3]);
                TMP_tmp4_2 = (PInt)(((PInt)((IPValue)TMP_tmp3_2)?.Clone()));
                expected = TMP_tmp4_2;
            }
            TMP_tmp5_2 = (PInt)(((PNamedTuple)payload_1)["value"]);
            TMP_tmp6_2 = (PBool)((PValues.SafeEquals(TMP_tmp5_2,expected)));
            if (TMP_tmp6_2)
            {
            }
            else
            {
                TMP_tmp7_2 = (PString)(((PString) String.Format("PSpec/Spec.p:20:13")));
                TMP_tmp8_2 = (PInt)(((PNamedTuple)payload_1)["key"]);
                TMP_tmp9_2 = (PInt)(((PNamedTuple)payload_1)["value"]);
                TMP_tmp10_2 = (PInt)(((PInt)((IPValue)expected)?.Clone()));
                TMP_tmp11_2 = (PString)(((PString) String.Format("VIOLATION: direct read key={0} returned {1} but storage has {2}",TMP_tmp8_2,TMP_tmp9_2,TMP_tmp10_2)));
                TMP_tmp12_1 = (PString)(((PString) String.Format("{0} {1}",TMP_tmp7_2,TMP_tmp11_2)));
                currentMachine.Assert(TMP_tmp6_2,"Assertion Failed: " + TMP_tmp12_1);
            }
        }
        [Start]
        [OnEventDoAction(typeof(eMonitorDbWrite), nameof(Anon_2))]
        [OnEventDoAction(typeof(eMonitorDirectRead), nameof(Anon_3))]
        class Watching : State
        {
        }
    }
}
namespace PImplementation
{
    internal partial class DirectClient : StateMachine
    {
        private PMachineValue db = null;
        private PInt clientId = ((PInt)0);
        private PInt numOps = ((PInt)0);
        private PInt opsIssued = ((PInt)0);
        public class ConstructorEvent : Event{public ConstructorEvent(IPValue val) : base(val) { }}
        
        protected override Event GetConstructorEvent(IPValue value) { return new ConstructorEvent((IPValue)value); }
        public DirectClient() {
            this.sends.Add(nameof(eMonitorDbWrite));
            this.sends.Add(nameof(eMonitorDirectRead));
            this.sends.Add(nameof(eRead));
            this.sends.Add(nameof(eReadResp));
            this.sends.Add(nameof(eWrite));
            this.sends.Add(nameof(eWriteResp));
            this.sends.Add(nameof(PHalt));
            this.receives.Add(nameof(eMonitorDbWrite));
            this.receives.Add(nameof(eMonitorDirectRead));
            this.receives.Add(nameof(eRead));
            this.receives.Add(nameof(eReadResp));
            this.receives.Add(nameof(eWrite));
            this.receives.Add(nameof(eWriteResp));
            this.receives.Add(nameof(PHalt));
        }
        
        public void Anon_4(Event currentMachine_dequeuedEvent)
        {
            DirectClient currentMachine = this;
            PNamedTuple p = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            PMachineValue TMP_tmp0_4 = null;
            PMachineValue TMP_tmp1_4 = null;
            PInt TMP_tmp2_4 = ((PInt)0);
            PInt TMP_tmp3_3 = ((PInt)0);
            PInt TMP_tmp4_3 = ((PInt)0);
            PInt TMP_tmp5_3 = ((PInt)0);
            TMP_tmp0_4 = (PMachineValue)(((PNamedTuple)p)["db"]);
            TMP_tmp1_4 = (PMachineValue)(((PMachineValue)((IPValue)TMP_tmp0_4)?.Clone()));
            db = TMP_tmp1_4;
            TMP_tmp2_4 = (PInt)(((PNamedTuple)p)["id"]);
            TMP_tmp3_3 = (PInt)(((PInt)((IPValue)TMP_tmp2_4)?.Clone()));
            clientId = TMP_tmp3_3;
            TMP_tmp4_3 = (PInt)(((PNamedTuple)p)["numOps"]);
            TMP_tmp5_3 = (PInt)(((PInt)((IPValue)TMP_tmp4_3)?.Clone()));
            numOps = TMP_tmp5_3;
            opsIssued = (PInt)(((PInt)(0)));
            currentMachine.RaiseGotoStateEvent<Issuing>();
            return;
        }
        public void Anon_5(Event currentMachine_dequeuedEvent)
        {
            DirectClient currentMachine = this;
            PInt key = ((PInt)0);
            PBool TMP_tmp0_5 = ((PBool)false);
            PInt TMP_tmp1_5 = ((PInt)0);
            PInt TMP_tmp2_5 = ((PInt)0);
            PBool TMP_tmp3_4 = ((PBool)false);
            PInt TMP_tmp4_4 = ((PInt)0);
            PInt TMP_tmp5_4 = ((PInt)0);
            PString TMP_tmp6_3 = ((PString)"");
            PMachineValue TMP_tmp7_3 = null;
            Event TMP_tmp8_3 = null;
            PMachineValue TMP_tmp9_3 = null;
            PInt TMP_tmp10_3 = ((PInt)0);
            PNamedTuple TMP_tmp11_3 = (new PNamedTuple(new string[]{"client","key"},null, ((PInt)0)));
            PInt TMP_tmp12_2 = ((PInt)0);
            PInt TMP_tmp13_1 = ((PInt)0);
            PInt TMP_tmp14 = ((PInt)0);
            PInt TMP_tmp15 = ((PInt)0);
            PString TMP_tmp16 = ((PString)"");
            PMachineValue TMP_tmp17 = null;
            Event TMP_tmp18 = null;
            PMachineValue TMP_tmp19 = null;
            PInt TMP_tmp20 = ((PInt)0);
            PInt TMP_tmp21 = ((PInt)0);
            PInt TMP_tmp22 = ((PInt)0);
            PNamedTuple TMP_tmp23 = (new PNamedTuple(new string[]{"client","key","value"},null, ((PInt)0), ((PInt)0)));
            PInt TMP_tmp24 = ((PInt)0);
            TMP_tmp0_5 = (PBool)((opsIssued) >= (numOps));
            if (TMP_tmp0_5)
            {
                currentMachine.RaiseGotoStateEvent<Done>();
                return;
                return ;
            }
            TMP_tmp1_5 = (PInt)(((PInt)currentMachine.TryRandom(((PInt)(3)))));
            TMP_tmp2_5 = (PInt)((((PInt)(40))) + (TMP_tmp1_5));
            key = TMP_tmp2_5;
            TMP_tmp3_4 = (PBool)(((PBool)currentMachine.RandomBoolean()));
            if (TMP_tmp3_4)
            {
                TMP_tmp4_4 = (PInt)(((PInt)((IPValue)clientId)?.Clone()));
                TMP_tmp5_4 = (PInt)(((PInt)((IPValue)key)?.Clone()));
                TMP_tmp6_3 = (PString)(((PString) String.Format("DirectClient {0}: READ  key={1}",TMP_tmp4_4,TMP_tmp5_4)));
                currentMachine.LogLine("" + TMP_tmp6_3);
                TMP_tmp7_3 = (PMachineValue)(((PMachineValue)((IPValue)db)?.Clone()));
                TMP_tmp8_3 = (Event)(new eRead((new PNamedTuple(new string[]{"client","key"},null, ((PInt)0)))));
                TMP_tmp9_3 = (PMachineValue)(currentMachine.self);
                TMP_tmp10_3 = (PInt)(((PInt)((IPValue)key)?.Clone()));
                TMP_tmp11_3 = (PNamedTuple)((new PNamedTuple(new string[]{"client","key"}, TMP_tmp9_3, TMP_tmp10_3)));
                TMP_tmp8_3.Payload = TMP_tmp11_3;
                currentMachine.SendEvent(TMP_tmp7_3, (Event)TMP_tmp8_3);
            }
            else
            {
                TMP_tmp12_2 = (PInt)(((PInt)((IPValue)clientId)?.Clone()));
                TMP_tmp13_1 = (PInt)(((PInt)((IPValue)key)?.Clone()));
                TMP_tmp14 = (PInt)((clientId) * (((PInt)(100))));
                TMP_tmp15 = (PInt)((TMP_tmp14) + (opsIssued));
                TMP_tmp16 = (PString)(((PString) String.Format("DirectClient {0}: WRITE key={1} val={2}",TMP_tmp12_2,TMP_tmp13_1,TMP_tmp15)));
                currentMachine.LogLine("" + TMP_tmp16);
                TMP_tmp17 = (PMachineValue)(((PMachineValue)((IPValue)db)?.Clone()));
                TMP_tmp18 = (Event)(new eWrite((new PNamedTuple(new string[]{"client","key","value"},null, ((PInt)0), ((PInt)0)))));
                TMP_tmp19 = (PMachineValue)(currentMachine.self);
                TMP_tmp20 = (PInt)(((PInt)((IPValue)key)?.Clone()));
                TMP_tmp21 = (PInt)((clientId) * (((PInt)(100))));
                TMP_tmp22 = (PInt)((TMP_tmp21) + (opsIssued));
                TMP_tmp23 = (PNamedTuple)((new PNamedTuple(new string[]{"client","key","value"}, TMP_tmp19, TMP_tmp20, TMP_tmp22)));
                TMP_tmp18.Payload = TMP_tmp23;
                currentMachine.SendEvent(TMP_tmp17, (Event)TMP_tmp18);
            }
            TMP_tmp24 = (PInt)((opsIssued) + (((PInt)(1))));
            opsIssued = TMP_tmp24;
        }
        public void Anon_6(Event currentMachine_dequeuedEvent)
        {
            DirectClient currentMachine = this;
            PNamedTuple resp = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            currentMachine.RaiseGotoStateEvent<Issuing>();
            return;
        }
        public void Anon_7(Event currentMachine_dequeuedEvent)
        {
            DirectClient currentMachine = this;
            PNamedTuple resp_1 = (PNamedTuple)(gotoPayload ?? ((Event)currentMachine_dequeuedEvent).Payload);
            this.gotoPayload = null;
            currentMachine.RaiseGotoStateEvent<Issuing>();
            return;
        }
        [Start]
        [OnEntry(nameof(Anon_4))]
        class Init : State
        {
        }
        [OnEntry(nameof(Anon_5))]
        [OnEventDoAction(typeof(eReadResp), nameof(Anon_6))]
        [OnEventDoAction(typeof(eWriteResp), nameof(Anon_7))]
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
        private PMachineValue db_1 = null;
        private PMachineValue client0 = null;
        private PMachineValue client1 = null;
        public class ConstructorEvent : Event{public ConstructorEvent(IPValue val) : base(val) { }}
        
        protected override Event GetConstructorEvent(IPValue value) { return new ConstructorEvent((IPValue)value); }
        public TestDriver() {
            this.sends.Add(nameof(eMonitorDbWrite));
            this.sends.Add(nameof(eMonitorDirectRead));
            this.sends.Add(nameof(eRead));
            this.sends.Add(nameof(eReadResp));
            this.sends.Add(nameof(eWrite));
            this.sends.Add(nameof(eWriteResp));
            this.sends.Add(nameof(PHalt));
            this.receives.Add(nameof(eMonitorDbWrite));
            this.receives.Add(nameof(eMonitorDirectRead));
            this.receives.Add(nameof(eRead));
            this.receives.Add(nameof(eReadResp));
            this.receives.Add(nameof(eWrite));
            this.receives.Add(nameof(eWriteResp));
            this.receives.Add(nameof(PHalt));
            this.creates.Add(nameof(I_DirectClient));
            this.creates.Add(nameof(I_SimpleTiDB));
        }
        
        public void Anon_8(Event currentMachine_dequeuedEvent)
        {
            TestDriver currentMachine = this;
            PMachineValue TMP_tmp0_6 = null;
            PMachineValue TMP_tmp1_6 = null;
            PInt TMP_tmp2_6 = ((PInt)0);
            PInt TMP_tmp3_5 = ((PInt)0);
            PNamedTuple TMP_tmp4_5 = (new PNamedTuple(new string[]{"db","id","numOps"},null, ((PInt)0), ((PInt)0)));
            PMachineValue TMP_tmp5_5 = null;
            PMachineValue TMP_tmp6_4 = null;
            PInt TMP_tmp7_4 = ((PInt)0);
            PInt TMP_tmp8_4 = ((PInt)0);
            PNamedTuple TMP_tmp9_4 = (new PNamedTuple(new string[]{"db","id","numOps"},null, ((PInt)0), ((PInt)0)));
            PMachineValue TMP_tmp10_4 = null;
            TMP_tmp0_6 = (PMachineValue)(currentMachine.CreateInterface<I_SimpleTiDB>( currentMachine));
            db_1 = (PMachineValue)TMP_tmp0_6;
            TMP_tmp1_6 = (PMachineValue)(((PMachineValue)((IPValue)db_1)?.Clone()));
            TMP_tmp2_6 = (PInt)(((PInt)(0)));
            TMP_tmp3_5 = (PInt)(((PInt)(5)));
            TMP_tmp4_5 = (PNamedTuple)((new PNamedTuple(new string[]{"db","id","numOps"}, TMP_tmp1_6, TMP_tmp2_6, TMP_tmp3_5)));
            TMP_tmp5_5 = (PMachineValue)(currentMachine.CreateInterface<I_DirectClient>( currentMachine, TMP_tmp4_5));
            client0 = (PMachineValue)TMP_tmp5_5;
            TMP_tmp6_4 = (PMachineValue)(((PMachineValue)((IPValue)db_1)?.Clone()));
            TMP_tmp7_4 = (PInt)(((PInt)(1)));
            TMP_tmp8_4 = (PInt)(((PInt)(5)));
            TMP_tmp9_4 = (PNamedTuple)((new PNamedTuple(new string[]{"db","id","numOps"}, TMP_tmp6_4, TMP_tmp7_4, TMP_tmp8_4)));
            TMP_tmp10_4 = (PMachineValue)(currentMachine.CreateInterface<I_DirectClient>( currentMachine, TMP_tmp9_4));
            client1 = (PMachineValue)TMP_tmp10_4;
            currentMachine.RaiseGotoStateEvent<Done>();
            return;
        }
        [Start]
        [OnEntry(nameof(Anon_8))]
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
    public class tcDirectTiDBLSI {
        public static void InitializeGlobalParams() {
        }
        public static void InitializeLinkMap() {
            PModule.linkMap.Clear();
            PModule.linkMap[nameof(I_TestDriver)] = new Dictionary<string, string>();
            PModule.linkMap[nameof(I_TestDriver)].Add(nameof(I_DirectClient), nameof(I_DirectClient));
            PModule.linkMap[nameof(I_TestDriver)].Add(nameof(I_SimpleTiDB), nameof(I_SimpleTiDB));
            PModule.linkMap[nameof(I_SimpleTiDB)] = new Dictionary<string, string>();
            PModule.linkMap[nameof(I_DirectClient)] = new Dictionary<string, string>();
        }
        
        public static void InitializeInterfaceDefMap() {
            PModule.interfaceDefinitionMap.Clear();
            PModule.interfaceDefinitionMap.Add(nameof(I_TestDriver), typeof(TestDriver));
            PModule.interfaceDefinitionMap.Add(nameof(I_SimpleTiDB), typeof(SimpleTiDB));
            PModule.interfaceDefinitionMap.Add(nameof(I_DirectClient), typeof(DirectClient));
        }
        
        public static void InitializeMonitorObserves() {
            PModule.monitorObserves.Clear();
            PModule.monitorObserves[nameof(LSISafety)] = new List<string>();
            PModule.monitorObserves[nameof(LSISafety)].Add(nameof(eMonitorDbWrite));
            PModule.monitorObserves[nameof(LSISafety)].Add(nameof(eMonitorDirectRead));
        }
        
        public static void InitializeMonitorMap(ControlledRuntime runtime) {
            PModule.monitorMap.Clear();
            PModule.monitorMap[nameof(I_TestDriver)] = new List<Type>();
            PModule.monitorMap[nameof(I_TestDriver)].Add(typeof(LSISafety));
            PModule.monitorMap[nameof(I_SimpleTiDB)] = new List<Type>();
            PModule.monitorMap[nameof(I_SimpleTiDB)].Add(typeof(LSISafety));
            PModule.monitorMap[nameof(I_DirectClient)] = new List<Type>();
            PModule.monitorMap[nameof(I_DirectClient)].Add(typeof(LSISafety));
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
    
    public class I_DirectClient : PMachineValue {
        public I_DirectClient (StateMachineId machine, List<string> permissions) : base(machine, permissions) { }
    }
    
    public class I_TestDriver : PMachineValue {
        public I_TestDriver (StateMachineId machine, List<string> permissions) : base(machine, permissions) { }
    }
    
    public partial class PHelper {
        public static void InitializeInterfaces() {
            PInterfaces.Clear();
            PInterfaces.AddInterface(nameof(I_SimpleTiDB), nameof(eMonitorDbWrite), nameof(eMonitorDirectRead), nameof(eRead), nameof(eReadResp), nameof(eWrite), nameof(eWriteResp), nameof(PHalt));
            PInterfaces.AddInterface(nameof(I_DirectClient), nameof(eMonitorDbWrite), nameof(eMonitorDirectRead), nameof(eRead), nameof(eReadResp), nameof(eWrite), nameof(eWriteResp), nameof(PHalt));
            PInterfaces.AddInterface(nameof(I_TestDriver), nameof(eMonitorDbWrite), nameof(eMonitorDirectRead), nameof(eRead), nameof(eReadResp), nameof(eWrite), nameof(eWriteResp), nameof(PHalt));
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
