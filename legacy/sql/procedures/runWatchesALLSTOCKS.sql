-- SqlProcedure: [dbo].[runWatchesALLSTOCKS]

set nocount on
BEGIN TRY
	declare @now datetime
	select @now = getdate()
	exec saveAudit @now, 'Running watches...Part 1'

	declare s cursor for
		select stockID from stock where active = 1 order by stockid asc

	declare @stockID int
	open s
	fetch next from s into @stockID
		while @@fetch_status=0
			begin
			Print @stockid
			exec runWatches @stockID, @startdate
			fetch next from s into @stockID
			end
	close s
	deallocate s
END TRY
BEGIN CATCH
	exec abecapError
END CATCH

set nocount off
