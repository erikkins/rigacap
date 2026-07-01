-- SqlProcedure: [dbo].[addWatchHistory]

set nocount on
declare @now datetime
select @now = getdate()

insert into WatchHistory(WatchID, RunDate, DataDate)
	values(@watchID, @now, @DataDate)

set nocount off
