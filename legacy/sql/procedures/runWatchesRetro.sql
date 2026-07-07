-- SqlProcedure: [dbo].[runWatchesRetro]

set nocount on
BEGIN TRY
	--run the watches that aren't dependent on the stockID
	declare @now2 datetime
	select @now2 = getdate()
	declare @txt varchar(500)
	select @txt = 'Running Retro watches for BuyID:' + Convert(varchar(10),@BuyID)
	exec saveAudit @now2, @txt
	declare @wid int, @procname varchar(500)
	declare @channelcount int, @curchannel char(1)
	declare @i int
	declare wcr cursor for
			select watchID, ProcName from Watch where Active = 1 and Action = 'R'
		open wcr
		fetch next from wcr into @wid, @procname
		while @@fetch_status=0
			begin
				exec @procname @BuyID=@BuyID								
			fetch next from wcr into @wid, @procname
			end
		close wcr
		deallocate wcr
END TRY
BEGIN CATCH
	exec abecapError
END CATCH

set nocount off
