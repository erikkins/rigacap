-- SqlProcedure: [dbo].[runWatchesRetroDate]

set nocount on
BEGIN TRY
	--run the watches that aren't dependent on the stockID
	declare @now2 datetime
	select @now2 = getdate()
	declare @txt varchar(500)
	--select @txt = 'Running Retro watches for BuyID:' + Convert(varchar(10),@BuyID)
	exec saveAudit @now2, @txt
	declare @wid int, @procname varchar(500)
	declare @channelcount int, @curchannel char(1)
	declare @i int
	declare @ret int
	declare @status int
	select @status = status from StockBuy where BuyID=@BuyID	
	select @ret=@status --was 0

	declare @dwapdate datetime
	select @dwapdate = dwapdate from stockbuy where buyID=@buyID

	
--only do the sells portion if the stock is still open
	if @ret = 0
	begin
	declare wcr cursor for
			select watchID, ProcName from Watch where Active = 1 and Action = 'D'
		open wcr
		fetch next from wcr into @wid, @procname
		while @@fetch_status=0
			begin
				--if @dwapdate is null
				--	begin
				--		Print 'Running ' + @procname
				--	end
				exec @ret = @procname @BuyID=@BuyID, @RunDate=@RunDate								
				if @ret=1
					begin
						--we sold, so we no longer need to run the rest of the procs
						if exists (select * from StockBuy where BuyID=@BuyID and status=0)
							begin
								Print 'False sell from ' + @procname
							end
						--else	
						--if @dwapdate is null
						--	begin
						--		Print 'Breaking on ' + @procname
						--	end
						break						
					end
			fetch next from wcr into @wid, @procname
			end
		close wcr
		deallocate wcr
	end

if @ret=1
	begin
	--now do the post sells
		declare @ret2 int
		select @ret2 = 0
		declare @wcr2 cursor 
			set @wcr2 = CURSOR local forward_only for
				select watchID, ProcName from Watch where Active = 1 and Action = 'P'
			open @wcr2
			fetch next from @wcr2 into @wid, @procname
			while @@fetch_status=0
				begin					
					exec @ret2 = @procname @BuyID=@BuyID, @RunDate=@RunDate								
					if @ret2=1
						begin
							--we sold, so we no longer need to run the rest of the procs
							if exists (select * from StockBuy where BuyID=@BuyID and status=0)
								begin
									Print 'False rebuy from ' + @procname
								end
							--else	
							--if @dwapdate is null
							--	begin
							--		Print 'Breaking on ' + @procname
							--	end
							break						
						end
				fetch next from @wcr2 into @wid, @procname
				end
			close @wcr2
			deallocate @wcr2
			if @ret2 = 0
				select @ret = 0
	end

		return @ret
END TRY
BEGIN CATCH
	Print ERROR_MESSAGE()
	exec abecapError
END CATCH

set nocount off
