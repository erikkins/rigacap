-- SqlProcedure: [dbo].[runWatches]

set nocount on
	declare @wid int, @procname varchar(500), @action char(1)

	declare wc cursor for
		select watchID, ProcName, Action from Watch where Active = 1 and Action not in ('A','R')
	open wc
	fetch next from wc into @wid, @procname, @action
		while @@fetch_status = 0
			begin
			if @action = 'B'
				begin				
					exec @procname @stockID=@stockID, @StartDate =@StartDate
				end
			else
				begin
					if @action = 'S'
						begin						
							exec @procname @stockID=@stockID
						end
					else
						begin
							if @action = 'N'
								begin
									exec @procname
								end
						end
				end
			fetch next from wc into @wid, @procname, @action
			end
	close wc
	deallocate wc
return
set nocount off
