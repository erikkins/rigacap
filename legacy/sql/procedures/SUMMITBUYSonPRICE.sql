-- SqlProcedure: [dbo].[SUMMITBUYSonPRICE]
-- header:
-- CREATE proc [dbo].[SUMMITBUYSonPRICE]

CREATE proc [dbo].[SUMMITBUYSonPRICE]
as
set nocount on

declare @52weekhighdate datetime
declare @52weekhigh money
declare @200dayhigh money
declare @currdate datetime
declare @currprice money
declare @currvolume bigint
declare @dwap money
declare @sid int
declare @buyID int
declare @50dmav bigint
declare @200Vol bigint

declare abcur cursor for 
	select stockID from stock where active=1 --and stockID = 7134

open abcur
fetch next from abcur into @sid
while @@fetch_status =0
	begin
		select @currdate = '3/1/2007'
		while @currdate < '2/24/2009'
			begin
				select @currprice = price, @currVolume = volume from stockdata where stockID=@sid and atwhen=@currdate
				if (@currprice is not null)
				BEGIN
					if dbo.fnIsPriceCrossDWAP(@sid,@currdate)=1 and dbo.isAccumulation(@sid,@currdate)=1
					bEGIN
					--only move on if the 50dmav is > 500K
					select @50dmav = dbo.fn50Volume(@sid, @currdate)
					if @50dmav >= 500000
						BeGiN					
							select @52weekhighdate = dbo.fn52WeekHighDate(@sid,@currdate)
							select @52weekhigh = price from stockdata where stockID=@sid and atwhen=@52weekhighdate
							if @52weekhigh > @currprice
								begin
								select @dwap = dbo.fnDWAP(@sid,@currdate)
								if @currprice > @dwap
									Begin
										select @200dayhigh = dbo.fn200DMA(@sid,@currdate)
										if @dwap > @200dayhigh
											BEGIN						
												select @200Vol = dbo.fn200Volume(@sid,@currdate)
												--print 'DWAP: ' + convert(varchar,@dwap) + '  50day: ' + convert(varchar,@50day) + '  50dayyest: ' + convert(varchar,@yest50day)
												if @currVolume > @200Vol
												begin
													exec @BuyID = AddBuyChannel @sid, -1000, @currdate, 'Summit Buy', null,100,'S',null,1
													exec findFirstSell @BuyID
													--select stockID, ticker, @currdate buydate
													--from stock where stockID=@sid
													
												end
											END
									end
								end
						EnD

					enD--ek
				END
			--move to the next day
			select @currdate = dateadd(day,1,@currdate)
			end
		fetch next from abcur into @sid
	end

close abcur
deallocate abcur

SET NOCOUNT OFF
