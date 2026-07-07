-- SqlProcedure: [dbo].[runWatchesVital]
-- header:
-- CREATE proc [dbo].[runWatchesVital]

CREATE proc [dbo].[runWatchesVital]
as
set nocount on
BEGIN TRY
	--run the watches that aren't dependent on the stockID
	declare @now2 datetime
	select @now2 = getdate()
	exec saveAudit @now2, 'Running watches...Part 2'
	declare @wid int, @procname varchar(500), @channel char(10)
	declare @channelcount int, @curchannel char(1)
	declare @i int
	declare wc cursor for
			select watchID, ProcName, channel from Watch where Active = 1 and Action = 'A'
		open wc
		fetch next from wc into @wid, @procname, @channel
		while @@fetch_status=0
			begin
				if @channel is null
					begin
						exec @procname
					end
				else
					begin
						select @channelcount = len(@channel)
						if @channelcount > 1
							begin
								--we must pull this apart substring and power through the channels
								select @i=1
								while @i <= @channelcount
									begin
										select @curchannel = substring(@channel,@i,1)
										exec @procname @channel = @curchannel
										select @i = @i + 1
									end
							end
						else
							begin
								exec @procname @channel = @channel
							end
					end
				
			fetch next from wc into @wid, @procname, @channel
			end
		close wc
		deallocate wc
END TRY
BEGIN CATCH
	exec abecapError
END CATCH

set nocount off
