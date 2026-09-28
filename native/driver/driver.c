/* Research prototype: not yet compiled with WDK or validated on Windows.
 * Synthetic HID descriptor, not a captured Elgato descriptor.
 * Never changes the physical D6 identity or firmware.
 */
#include <ntddk.h>
#include <wdf.h>
#include <hidport.h>
#include <vhf.h>
#include "bridge.h"
#include "identity.h"

static UCHAR Descriptor[] = {
    0x06,0x00,0xff, 0x09,0x01, 0xa1,0x01,
    0x15,0x00, 0x26,0xff,0x00, 0x75,0x08,
    0x85,0x01, 0x09,0x01, 0x95,0x12, 0x81,0x02,
    0x85,0x02, 0x09,0x01, 0x96,0xff,0x03, 0x91,0x02,
    0x85,0x03, 0x09,0x01, 0x95,0x1f, 0xb1,0x02,
    0x85,0x05, 0x09,0x01, 0x95,0x1f, 0xb1,0x02,
    0x85,0x06, 0x09,0x01, 0x95,0x1f, 0xb1,0x02, 0xc0
};
typedef struct {
    VHFHANDLE Vhf;
    WDFSPINLOCK Lock;
    WDFTIMER Watchdog;
    D6_EVENT *Ring;
    ULONG Head, Count, Dropped;
    UCHAR Keys[19];
    ULONGLONG LastSeen;
} CONTEXT;
WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(CONTEXT, Context)
DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD AddDevice;
EVT_WDF_OBJECT_CONTEXT_CLEANUP Cleanup;
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL Ioctl;
EVT_WDF_FILE_CLEANUP FileCleanup;
EVT_WDF_TIMER Timer;
EVT_VHF_ASYNC_OPERATION GetFeature, SetFeature, WriteReport, GetInput;

static NTSTATUS Push(CONTEXT *c, ULONG kind, PHID_XFER_PACKET p) {
    D6_EVENT *e;
    if (!p->reportBuffer || p->reportBufferLen > 1024 || !p->reportBufferLen)
        return STATUS_INVALID_BUFFER_SIZE;
    WdfSpinLockAcquire(c->Lock);
    if (c->Count == D6_RING_SIZE) {
        ++c->Dropped;
        WdfSpinLockRelease(c->Lock);
        return STATUS_DEVICE_BUSY;
    }
    e = &c->Ring[(c->Head + c->Count) % D6_RING_SIZE];
    RtlZeroMemory(e, sizeof(*e));
    e->Kind = kind;
    e->Length = p->reportBufferLen;
    RtlCopyMemory(e->Data, p->reportBuffer, p->reportBufferLen);
    ++c->Count;
    WdfSpinLockRelease(c->Lock);
    return STATUS_SUCCESS;
}
static NTSTATUS Submit(CONTEXT *c, UCHAR *data) {
    HID_XFER_PACKET p;
    p.reportId = 1; p.reportBuffer = data; p.reportBufferLen = 19;
    return VhfReadReportSubmit(c->Vhf, &p);
}
static VOID ReleaseKeys(CONTEXT *c) {
    UCHAR data[19];
    WdfSpinLockAcquire(c->Lock);
    RtlZeroMemory(c->Keys+4, 15);
    RtlCopyMemory(data, c->Keys, sizeof(data));
    WdfSpinLockRelease(c->Lock);
    if (c->Vhf) (void)Submit(c, data);
}
VOID FileCleanup(WDFFILEOBJECT f) { ReleaseKeys(Context(WdfFileObjectGetDevice(f))); }
VOID Timer(WDFTIMER timer) {
    CONTEXT *c = Context(WdfTimerGetParentObject(timer));
    BOOLEAN release = FALSE;
    ULONG i;
    WdfSpinLockAcquire(c->Lock);
    if (KeQueryInterruptTime() - c->LastSeen > 30000000ULL)
        for (i=4; i<19; ++i) if (c->Keys[i]) { release=TRUE; break; }
    WdfSpinLockRelease(c->Lock);
    if (release) ReleaseKeys(c);
}
VOID WriteReport(PVOID ctx, VHFOPERATIONHANDLE op, PVOID extra, PHID_XFER_PACKET p) {
    UNREFERENCED_PARAMETER(extra);
    VhfAsyncOperationComplete(op, Push((CONTEXT*)ctx, 1, p));
}
VOID SetFeature(PVOID ctx, VHFOPERATIONHANDLE op, PVOID extra, PHID_XFER_PACKET p) {
    NTSTATUS s;
    UNREFERENCED_PARAMETER(extra);
    s = Push((CONTEXT*)ctx, 2, p);
    if (NT_SUCCESS(s)) {
        if (p->reportId!=3 || p->reportBufferLen<2) s=STATUS_NOT_SUPPORTED;
        else switch(p->reportBuffer[1]) {
            case 2: case 5: case 6: case 8: break;
            default: s=STATUS_NOT_SUPPORTED; break;
        }
    }
    VhfAsyncOperationComplete(op, s);
}
VOID GetFeature(PVOID ctx, VHFOPERATIONHANDLE op, PVOID extra, PHID_XFER_PACKET p) {
    NTSTATUS s = STATUS_SUCCESS;
    UNREFERENCED_PARAMETER(extra);
    // Log only the requested ID, never uninitialized request payload bytes.
    UCHAR id = p->reportId;
    HID_XFER_PACKET log;
    log.reportId=id; log.reportBuffer=&id; log.reportBufferLen=1;
    (void)Push((CONTEXT*)ctx, 3, &log);
    if (!p->reportBuffer || p->reportBufferLen < 32) s=STATUS_BUFFER_TOO_SMALL;
    else {
        if (D6Identity(id,p->reportBuffer,p->reportBufferLen)!=1)
            s=STATUS_NOT_SUPPORTED;
    }
    VhfAsyncOperationComplete(op, s);
}
VOID GetInput(PVOID ctx, VHFOPERATIONHANDLE op, PVOID extra, PHID_XFER_PACKET p) {
    CONTEXT *c=(CONTEXT*)ctx;
    NTSTATUS s=STATUS_SUCCESS;
    UNREFERENCED_PARAMETER(extra);
    if (p->reportId!=1 || !p->reportBuffer || p->reportBufferLen<19)
        s=STATUS_INVALID_PARAMETER;
    else {
        RtlZeroMemory(p->reportBuffer, p->reportBufferLen);
        WdfSpinLockAcquire(c->Lock);
        RtlCopyMemory(p->reportBuffer,c->Keys,19);
        WdfSpinLockRelease(c->Lock);
    }
    VhfAsyncOperationComplete(op,s);
}
VOID Ioctl(WDFQUEUE q, WDFREQUEST r, size_t outLen, size_t inLen, ULONG code) {
    CONTEXT *c=Context(WdfIoQueueGetDevice(q));
    NTSTATUS s=STATUS_INVALID_DEVICE_REQUEST;
    size_t done=0;
    PVOID buffer;
    ULONG n, i;
    UCHAR report[19];
    UNREFERENCED_PARAMETER(inLen);
    if (code==IOCTL_D6_KEYS) {
        s=WdfRequestRetrieveInputBuffer(r,19,&buffer,NULL);
        if (NT_SUCCESS(s)) {
            RtlCopyMemory(report,buffer,19);
            if (report[0]!=1 || report[1]!=0 || report[2]!=15 || report[3]!=0)
                s=STATUS_INVALID_PARAMETER;
            for(i=4; i<19; ++i) if(report[i]>1) s=STATUS_INVALID_PARAMETER;
            if (NT_SUCCESS(s)) {
                WdfSpinLockAcquire(c->Lock);
                RtlCopyMemory(c->Keys,report,19);
                WdfSpinLockRelease(c->Lock);
                s=Submit(c,report);
            }
        }
    } else if (code==IOCTL_D6_POLL) {
        s=WdfRequestRetrieveOutputBuffer(r,sizeof(D6_EVENT),&buffer,NULL);
        if (NT_SUCCESS(s)) {
            WdfSpinLockAcquire(c->Lock);
            n=(ULONG)min(outLen/sizeof(D6_EVENT),(size_t)c->Count);
            // Limit work under the spin lock, even for a large caller buffer.
            n=min(n,16);
            for(i=0;i<n;++i) {
                RtlCopyMemory((D6_EVENT*)buffer+i,&c->Ring[c->Head],sizeof(D6_EVENT));
                c->Head=(c->Head+1)%D6_RING_SIZE; --c->Count;
            }
            c->LastSeen=KeQueryInterruptTime();
            WdfSpinLockRelease(c->Lock);
            done=n*sizeof(D6_EVENT);
        }
    } else if (code==IOCTL_D6_STATS) {
        s=WdfRequestRetrieveOutputBuffer(r,sizeof(D6_STATS),&buffer,NULL);
        if (NT_SUCCESS(s)) {
            D6_STATS *stats=(D6_STATS*)buffer;
            WdfSpinLockAcquire(c->Lock);
            stats->Version=1; stats->Queued=c->Count; stats->Dropped=c->Dropped; stats->Reserved=0;
            WdfSpinLockRelease(c->Lock);
            done=sizeof(D6_STATS);
        }
    }
    WdfRequestCompleteWithInformation(r,s,NT_SUCCESS(s)?done:0);
}
VOID Cleanup(WDFOBJECT device) {
    CONTEXT *c=Context(device);
    if(c->Watchdog) WdfTimerStop(c->Watchdog,TRUE);
    if(c->Vhf) { VhfDelete(c->Vhf,TRUE); c->Vhf=NULL; }
}
NTSTATUS AddDevice(WDFDRIVER driver, PWDFDEVICE_INIT init) {
    WDFDEVICE device;
    WDF_OBJECT_ATTRIBUTES a, child;
    WDF_IO_QUEUE_CONFIG queue;
    WDF_FILEOBJECT_CONFIG file;
    WDF_TIMER_CONFIG timer;
    WDFMEMORY memory;
    VHF_CONFIG vhf;
    NTSTATUS s;
    CONTEXT *c;
    DECLARE_CONST_UNICODE_STRING(name,L"\\Device\\D6VirtualDeck");
    DECLARE_CONST_UNICODE_STRING(link,L"\\DosDevices\\D6VirtualDeck");
    DECLARE_CONST_UNICODE_STRING(sddl,L"D:P(A;;GA;;;SY)(A;;GA;;;BA)");
    UNREFERENCED_PARAMETER(driver);
    WdfDeviceInitSetDeviceType(init,FILE_DEVICE_UNKNOWN);
    WdfDeviceInitSetCharacteristics(init,FILE_DEVICE_SECURE_OPEN,FALSE);
    WdfDeviceInitSetExclusive(init,TRUE);
    s=WdfDeviceInitAssignName(init,&name); if(!NT_SUCCESS(s))return s;
    s=WdfDeviceInitAssignSDDLString(init,&sddl); if(!NT_SUCCESS(s))return s;
    WDF_FILEOBJECT_CONFIG_INIT(&file,WDF_NO_EVENT_CALLBACK,WDF_NO_EVENT_CALLBACK,FileCleanup);
    WdfDeviceInitSetFileObjectConfig(init,&file,WDF_NO_OBJECT_ATTRIBUTES);
    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&a,CONTEXT);
    a.EvtCleanupCallback=Cleanup;
    a.ExecutionLevel=WdfExecutionLevelPassive;
    s=WdfDeviceCreate(&init,&a,&device); if(!NT_SUCCESS(s))return s;
    c=Context(device); c->Keys[0]=1; c->Keys[2]=15;
    WDF_OBJECT_ATTRIBUTES_INIT(&child); child.ParentObject=device;
    s=WdfSpinLockCreate(&child,&c->Lock); if(!NT_SUCCESS(s))return s;
    s=WdfMemoryCreate(&child,NonPagedPoolNx,'6DvD',sizeof(D6_EVENT)*D6_RING_SIZE,&memory,(PVOID*)&c->Ring);
    if(!NT_SUCCESS(s))return s;
    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&queue,WdfIoQueueDispatchSequential);
    queue.EvtIoDeviceControl=Ioctl;
    s=WdfIoQueueCreate(device,&queue,WDF_NO_OBJECT_ATTRIBUTES,NULL); if(!NT_SUCCESS(s))return s;
    s=WdfDeviceCreateSymbolicLink(device,&link); if(!NT_SUCCESS(s))return s;
    VHF_CONFIG_INIT(&vhf,WdfDeviceWdmGetDeviceObject(device),sizeof(Descriptor),Descriptor);
    vhf.VhfClientContext=c; vhf.VendorID=0x0fd9; vhf.ProductID=0x006d; vhf.VersionNumber=0x0100;
    vhf.EvtVhfAsyncOperationGetFeature=GetFeature;
    vhf.EvtVhfAsyncOperationSetFeature=SetFeature;
    vhf.EvtVhfAsyncOperationWriteReport=WriteReport;
    vhf.EvtVhfAsyncOperationGetInputReport=GetInput;
    s=VhfCreate(&vhf,&c->Vhf); if(!NT_SUCCESS(s))return s;
    s=VhfStart(c->Vhf); if(!NT_SUCCESS(s))return s;
    WDF_TIMER_CONFIG_INIT_PERIODIC(&timer,Timer,1000);
    timer.AutomaticSerialization=FALSE;
    // Periodic WDF timers cannot run at PASSIVE_LEVEL. Override parent inheritance.
    child.ExecutionLevel=WdfExecutionLevelDispatch;
    s=WdfTimerCreate(&timer,&child,&c->Watchdog); if(!NT_SUCCESS(s))return s;
    c->LastSeen=KeQueryInterruptTime();
    WdfTimerStart(c->Watchdog,WDF_REL_TIMEOUT_IN_MS(1000));
    return STATUS_SUCCESS;
}
NTSTATUS DriverEntry(PDRIVER_OBJECT object, PUNICODE_STRING path) {
    WDF_DRIVER_CONFIG cfg;
    WDF_DRIVER_CONFIG_INIT(&cfg,AddDevice);
    return WdfDriverCreate(object,path,WDF_NO_OBJECT_ATTRIBUTES,&cfg,WDF_NO_HANDLE);
}
